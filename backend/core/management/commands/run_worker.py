import logging

import redis
from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import CarePlan
# views.py 里已经建好的 Anthropic client 和 prompt 模板, 注释里就写着"留给 worker", 直接复用。
from careplan_project.views import client, PROMPT_TEMPLATE

logger = logging.getLogger("careplan_project")


class Command(BaseCommand):
    help = "手写 worker: 从 Redis 队列取 care plan id, 调 LLM 生成, 写回数据库。"

    def handle(self, *args, **options):
        # worker 自己连一条 redis, 它是队列的"消费方"。
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )
        self.stdout.write(f"worker started, waiting on '{settings.CAREPLAN_QUEUE}' ...")

        while True:
            # views.py 用 rpush 从右边推入, 这里从左边阻塞取 -> FIFO。
            # blpop 队列空时会阻塞等待, 不会空转 CPU; 返回 (队列名, 值)。
            _, care_plan_id = r.blpop(settings.CAREPLAN_QUEUE)
            self.stdout.write(f"got care plan id={care_plan_id}")
            self.process(care_plan_id)

    def process(self, care_plan_id):
        # 用 id 查出 care plan 和它关联的 order / patient / provider。
        care_plan = CarePlan.objects.select_related(
            "order", "order__patient", "order__provider"
        ).get(id=care_plan_id)

        # 标记成 processing, 表示 worker 已经接手 (前端此时刷新能看到"处理中")。
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
            self.stdout.write(f"care plan {care_plan_id} -> completed")
        except Exception as e:
            # 失败: 状态改 failed (内容留空)。
            care_plan.status = CarePlan.Status.FAILED
            care_plan.save(update_fields=["status"])
            self.stdout.write(f"care plan {care_plan_id} -> failed: {e}")
