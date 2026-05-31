"""测试夹具 (Day 8 Part 3)。

两件公共事:
1. 把 Celery 的 generate_care_plan.delay 换成假的 —— 测试里不真的入队、
   不跑 worker、不调 LLM (满足 "不真的触发 Celery / 不真的调用 LLM")。
2. 提供构造测试数据的 helper:
   - make_data():    给 service 层用的后端字段 dict (snake_case, 带 dob)。
   - make_payload(): 给 view 层用的前端 POST body (camelCase)。
"""
from datetime import date

import pytest


@pytest.fixture(autouse=True)
def mock_celery_delay(monkeypatch):
    """拦截 generate_care_plan.delay, 让它什么都不做。

    service.create_order 末尾会 `from core.tasks import generate_care_plan`
    再 `.delay(...)`。这里直接替换 task 对象上的 delay 方法, 返回一个
    MagicMock, 测试需要时可以断言它被调用过几次。autouse=True -> 每个测试自动生效。
    """
    from unittest.mock import MagicMock
    from core import tasks

    fake_delay = MagicMock(name="generate_care_plan.delay")
    monkeypatch.setattr(tasks.generate_care_plan, "delay", fake_delay)
    return fake_delay


def make_data(**overrides):
    """service.create_order 期望的后端字段 dict (已解析好的格式)。

    注意: 真实 HTTP 路径上 serializer 不传 dob (data.get('dob') 永远是 None),
    但 service 内部会读 dob 做身份匹配, 所以单元测试这里显式带上 dob,
    才能覆盖 "名字+DOB" 相关的规则。
    """
    data = {
        "mrn": "100001",
        "first_name": "Alice",
        "last_name": "Smith",
        "npi": "1234567890",
        "provider_name": "Dr. Jones",
        "medication": "Humira",
        "primary_diagnosis": "K50.00",
        "additional_diagnosis": [],
        "medication_history": [],
        "patient_records": "",
        "dob": date(1990, 1, 1),
    }
    data.update(overrides)
    return data


def make_payload(**overrides):
    """view 层 POST /api/orders/ 的前端 body (camelCase)。"""
    payload = {
        "mrn": "100001",
        "firstName": "Alice",
        "lastName": "Smith",
        "npi": "1234567890",
        "provider": "Dr. Jones",
        "medication": "Humira",
        "diagnosis": "K50.00",
        "additionalDiagnosis": [],
        "medicationHistory": [],
        "patientRecords": "",
    }
    payload.update(overrides)
    return payload
