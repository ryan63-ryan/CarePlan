import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from core.models import CarePlan
# 复用 services.py 里已经建好的 Anthropic client 和 prompt 模板。
# (restructure 时 client/PROMPT_TEMPLATE 从 views.py 挪到了 services.py,
#  这里的 import 路径之前没跟着改 -> 修正。)
from core.services import client, PROMPT_TEMPLATE

logger = logging.getLogger("careplan_project")


@shared_task(bind=True, max_retries=3)
def generate_care_plan(self, care_plan_id):
    # 找不到记录会抛 DoesNotExist。它在 try 之外 -> 只让这个 task 失败,
    # 不重试(重试也没用)、更不会把 worker 搞崩。这正是 Celery 比手写 worker 强的地方。
    care_plan = CarePlan.objects.select_related(
        "order", "order__patient", "order__provider"
    ).get(id=care_plan_id)

    # 标记 processing, 表示 worker 已接手 (前端此时刷新能看到"处理中")。
    care_plan.status = CarePlan.Status.PROCESSING
    care_plan.save(update_fields=["status"])

    try:
        order = care_plan.order
        prompt = PROMPT_TEMPLATE.format(
            first_name=order.patient.first_name,
            last_name=order.patient.last_name,
            mrn=order.patient.mrn,
            provider=order.provider.name,
            npi=order.provider.npi,
            diagnosis=order.primary_diagnosis,
            medication=order.medication,
            additional_diagnosis=order.additional_diagnosis,
            medication_history=order.medication_history,
            patient_records=order.patient_records,
        )
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        # 成功: 写回内容, 状态改 completed。
        care_plan.content = message.content[0].text
        care_plan.status = CarePlan.Status.COMPLETED
        care_plan.save(update_fields=["content", "status"])
        logger.info("care plan %s -> completed", care_plan_id)
    except Exception as exc:
        logger.warning(
            "care plan %s attempt %s failed: %s",
            care_plan_id, self.request.retries + 1, exc,
        )
        try:
            # 指数退避: 第 1/2/3 次重试分别等 2s / 4s / 8s 再重新入队执行。
            raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))
        except MaxRetriesExceededError:
            # 3 次重试都失败 -> 标记 failed。
            care_plan.status = CarePlan.Status.FAILED
            care_plan.save(update_fields=["status"])
            logger.error("care plan %s -> failed after 3 retries", care_plan_id)
