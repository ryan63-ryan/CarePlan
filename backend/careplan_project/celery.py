import os

from celery import Celery

# Celery 子进程也要知道用哪个 Django settings。
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "careplan_project.settings")

app = Celery("careplan_project")
# 从 Django settings 读配置, 只认 CELERY_ 开头的键 (如 CELERY_BROKER_URL -> broker_url)。
app.config_from_object("django.conf:settings", namespace="CELERY")
# 自动扫描每个 INSTALLED_APPS 下的 tasks.py, 注册里面的 @shared_task。
app.autodiscover_tasks()
