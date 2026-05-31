"""Integration tests: view + middleware 的完整 HTTP 路径 (Day 8 Part 3)。

用 Django test client 真打 POST /api/orders/, 验证:
  - 正常单返回 200 + carePlanId;
  - service 抛的 DuplicateBlocked/Warning 异常被 core.middleware 接住,
    转成统一 JSON (code/type/message/warnings/requires_confirmation)。
Celery .delay 已由 conftest.py 夹具 mock, 不真触发任务、不调 LLM。
"""
import json

import pytest

from .conftest import make_payload

pytestmark = pytest.mark.django_db

ORDERS_URL = "/api/orders/"


def _post(client, payload):
    return client.post(
        ORDERS_URL,
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_post_valid_order_returns_200_with_careplan_id(client):
    """正常订单 -> 200, body 带 carePlanId + status。"""
    resp = _post(client, make_payload())

    assert resp.status_code == 200
    body = resp.json()
    assert "carePlanId" in body
    assert body["carePlanId"] is not None
    assert body["status"] == "pending"


def test_post_blocked_duplicate_returns_409_unified_json(client):
    """NPI 撞名 -> BlockedException -> 409, 统一 JSON 格式。"""
    # 先建一个 Provider (NPI 1234567890 -> Dr. Jones)。
    assert _post(client, make_payload()).status_code == 200

    # 同 NPI 换个名字 -> 硬阻止。
    resp = _post(client, make_payload(provider="Dr. Imposter"))

    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "DUPLICATE_BLOCKED"
    assert body["type"] == "block"
    assert body["message"]  # 非空
    assert body["warnings"] == []


def test_post_warning_duplicate_returns_409_requires_confirmation(client):
    """MRN 撞名 -> WarningException -> 409 + requires_confirmation: true。"""
    # 先建一个 Patient (MRN 100001 -> Alice Smith)。
    assert _post(client, make_payload()).status_code == 200

    # 同 MRN 换个名字 (provider 仍同 NPI 同名 -> 复用, 不会先被 block 拦下)。
    resp = _post(client, make_payload(firstName="Bob"))

    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "DUPLICATE_WARNING"
    assert body["type"] == "warning"
    assert body["requires_confirmation"] is True
    assert len(body["warnings"]) >= 1
