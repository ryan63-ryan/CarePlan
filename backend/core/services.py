"""业务逻辑层: 操作数据库、放 Celery/Redis 队列、调用 LLM。

不依赖 HTTP (不碰 request / 不返回 JsonResponse), 因此可被 view、Celery
task、management command、测试任意复用。
"""
import logging

from django.conf import settings
from anthropic import Anthropic

from core.models import Patient, Provider, Order, CarePlan

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


def create_order(data):
    """建订单 + 触发异步生成 care plan。data 是已转换好的后端字段 dict。"""
    logger.info(
        "parsed payload: patient=%s %s, medication=%s",
        data["first_name"],
        data["last_name"],
        data["medication"],
    )

    # 按 MRN / NPI 复用已存在的病人 / 医生, 不重复创建。
    patient, _ = Patient.objects.get_or_create(
        mrn=data["mrn"],
        defaults={
            "first_name": data["first_name"],
            "last_name": data["last_name"],
        },
    )
    provider, _ = Provider.objects.get_or_create(
        npi=data["npi"],
        defaults={"name": data["provider_name"]},
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
