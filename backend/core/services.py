"""业务逻辑层: 操作数据库、放 Celery/Redis 队列、调用 LLM。

不依赖 HTTP (不碰 request / 不返回 JsonResponse), 因此可被 view、Celery
task、management command、测试任意复用。
"""
import logging

from django.conf import settings
from django.utils import timezone
from anthropic import Anthropic

from core.models import Patient, Provider, Order, CarePlan
# 重复检测异常: 只管 raise, 统一格式由 core/middleware.py 处理。
from core.exceptions import DuplicateBlockedException, DuplicateWarningException

logger = logging.getLogger(__name__)

# Anthropic client 和 prompt 模板, 被 Celery 任务 (core/tasks.py) 复用。
client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

PROMPT_TEMPLATE = """You are a clinical pharmacist at a specialty pharmacy. Generate a care plan
for the patient below. The care plan MUST contain exactly these four sections,
in order, with these exact headings:

1. Problem list (Drug therapy problems)
2. Goals (SMART)
3. Pharmacist interventions / plan
4. Monitoring plan & lab schedule

Patient information:
- Name: {first_name} {last_name}
- MRN: {mrn}
- Referring Provider: {provider} (NPI: {npi})
- Primary Diagnosis (ICD-10): {diagnosis}
- Medication: {medication}
- Additional Diagnoses: {additional_diagnosis}
- Medication History: {medication_history}
- Patient Records: {patient_records}

Write the care plan now."""


def create_order(data, confirm=False):
    """建订单 + 触发异步生成 care plan。data 是已转换好的后端字段 dict。

    confirm=True 时跳过所有 DuplicateWarningException (软警告), 但
    DuplicateBlockedException (硬阻止) 无论如何都会抛出。
    """
    logger.info(
        "parsed payload: patient=%s %s, medication=%s",
        data["first_name"],
        data["last_name"],
        data["medication"],
    )

    # ------------------------------------------------------------------
    # Provider 重复检测 (NPI 全国唯一)。
    # ------------------------------------------------------------------
    existing_provider = Provider.objects.filter(npi=data["npi"]).first()
    if existing_provider is not None:
        if existing_provider.name == data["provider_name"]:
            # NPI 相同 + 名字相同 -> 复用现有。
            provider = existing_provider
            logger.info("provider duplicate: reusing existing NPI %s", data["npi"])
        else:
            # NPI 相同 + 名字不同 -> 必须阻止 (同一个执照号不可能是两个人)。
            raise DuplicateBlockedException(
                "NPI %s already belongs to '%s', cannot register it under '%s'"
                % (data["npi"], existing_provider.name, data["provider_name"])
            )
    else:
        provider = Provider.objects.create(
            npi=data["npi"],
            name=data["provider_name"],
        )

    # ------------------------------------------------------------------
    # Patient 重复检测 (MRN 唯一, 同时也看 名字+DOB 的身份匹配)。
    # ------------------------------------------------------------------
    dob = data.get("dob")
    existing_by_mrn = Patient.objects.filter(mrn=data["mrn"]).first()
    if existing_by_mrn is not None:
        same_name = (
            existing_by_mrn.first_name == data["first_name"]
            and existing_by_mrn.last_name == data["last_name"]
        )
        same_dob = existing_by_mrn.dob == dob
        if same_name and same_dob:
            # MRN 相同 + 名字和 DOB 都相同 -> 复用现有。
            patient = existing_by_mrn
            logger.info("patient duplicate: reusing existing MRN %s", data["mrn"])
        else:
            # MRN 相同 + 名字或 DOB 不同 -> 警告 (可能录错, 也可能 MRN 撞号)。
            if not confirm:
                raise DuplicateWarningException(
                    "MRN %s already exists as '%s %s' (dob=%s); "
                    "incoming '%s %s' (dob=%s) does not match"
                    % (
                        data["mrn"],
                        existing_by_mrn.first_name,
                        existing_by_mrn.last_name,
                        existing_by_mrn.dob,
                        data["first_name"],
                        data["last_name"],
                        dob,
                    )
                )
            # confirm=True: MRN 唯一, 无法再建一条同号, 只能复用这条记录。
            patient = existing_by_mrn
            logger.warning("patient duplicate (MRN mismatch) bypassed via confirm=True")
    else:
        # MRN 不存在, 再看是否有 名字+DOB 相同但 MRN 不同的病人。
        existing_by_identity = Patient.objects.filter(
            first_name=data["first_name"],
            last_name=data["last_name"],
            dob=dob,
        ).first()
        if existing_by_identity is not None:
            # 名字+DOB 相同 + MRN 不同 -> 警告 (疑似同一人用了两个 MRN)。
            if not confirm:
                raise DuplicateWarningException(
                    "patient '%s %s' (dob=%s) already exists under MRN %s; "
                    "incoming MRN %s is different"
                    % (
                        data["first_name"],
                        data["last_name"],
                        dob,
                        existing_by_identity.mrn,
                        data["mrn"],
                    )
                )
            logger.warning("patient duplicate (identity match) bypassed via confirm=True")
        patient = Patient.objects.create(
            mrn=data["mrn"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            dob=dob,
        )

    # ------------------------------------------------------------------
    # Order 重复检测 (同患者 + 同药物)。
    # ------------------------------------------------------------------
    # localdate() 取的是 TIME_ZONE (当前激活时区) 的今天, 和下面 created_at__date
    # 查找的口径一致 (__date 也会把 created_at 转成 TIME_ZONE 再取日期)。
    # 不能用 UTC 的当天日期去比 TIME_ZONE 的日期: 在 UTC 午夜后、本地午夜前的窗口里
    # 两者差一天 -> 同日订单查不到, 误判成"不同天"。
    today = timezone.localdate()
    same_day_order = Order.objects.filter(
        patient=patient,
        medication=data["medication"],
        created_at__date=today,
    ).first()
    if same_day_order is not None:
        # 同一患者 + 同一药物 + 同一天 -> 必须阻止 (重复下单)。
        raise DuplicateBlockedException(
            "order for '%s' on patient MRN %s already placed today (order #%s)"
            % (data["medication"], patient.mrn, same_day_order.pk)
        )
    prior_order = (
        Order.objects.filter(patient=patient, medication=data["medication"])
        .exclude(created_at__date=today)
        .order_by("-created_at")
        .first()
    )
    if prior_order is not None and not confirm:
        # 同一患者 + 同一药物 + 不同天 -> 警告 (confirm=True 跳过)。
        raise DuplicateWarningException(
            "patient MRN %s previously ordered '%s' on %s (order #%s)"
            % (
                patient.mrn,
                data["medication"],
                prior_order.created_at.date(),
                prior_order.pk,
            )
        )

    order = Order.objects.create(
        patient=patient,
        provider=provider,
        medication=data["medication"],
        primary_diagnosis=data["primary_diagnosis"],
        additional_diagnosis=data["additional_diagnosis"],
        medication_history=data["medication_history"],
        patient_records=data["patient_records"],
    )
    # 还没生成 care plan: 先建一条 pending 记录 (内容留空), 实际生成交给后台 worker。
    care_plan = CarePlan.objects.create(
        order=order,
        status=CarePlan.Status.PENDING,
    )

    # 触发 Celery 异步任务,把任务丢进 broker 后立刻返回
    from core.tasks import generate_care_plan
    generate_care_plan.delay(care_plan.id)
    logger.info("enqueued care plan %s via celery (status=pending)", care_plan.id)

    return care_plan


def get_care_plan(care_plan_id):
    """按 id 取 care plan (前端轮询用)。"""
    return CarePlan.objects.get(id=care_plan_id)


def get_order(order_id):
    """按 id 取订单详情, 一次性带出关联对象。"""
    return Order.objects.select_related("patient", "provider", "care_plan").get(id=order_id)
