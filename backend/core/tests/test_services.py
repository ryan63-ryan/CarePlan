"""Unit tests: service 层重复检测 (Day 8 Part 3)。

直接调用 services.create_order(), 不走 HTTP, 覆盖 7 条重复检测规则。
Celery 的 .delay 已由 conftest.py 的 autouse 夹具 mock 掉, 不会真触发任务。
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from core import services
from core.models import Patient, Provider, Order
from core.exceptions import DuplicateBlockedException, DuplicateWarningException

from .conftest import make_data

# 所有测试都要碰数据库。
pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Provider 规则
# ---------------------------------------------------------------------------
def test_provider_same_npi_same_name_reuses():
    """规则 1: NPI 相同 + 名字相同 -> 复用现有 Provider, 不新建。"""
    services.create_order(make_data())
    # 第二单: 同 NPI 同名, 换不同病人 + 不同药 (避免触发其它重复规则)。
    services.create_order(
        make_data(
            mrn="200002",
            first_name="Bob",
            last_name="Brown",
            medication="Enbrel",
        )
    )
    assert Provider.objects.count() == 1


def test_provider_same_npi_different_name_blocks():
    """规则 2: NPI 相同 + 名字不同 -> DuplicateBlockedException。"""
    services.create_order(make_data())
    with pytest.raises(DuplicateBlockedException):
        services.create_order(make_data(provider_name="Dr. Imposter"))


# ---------------------------------------------------------------------------
# Patient 规则
# ---------------------------------------------------------------------------
def test_patient_same_mrn_same_identity_reuses():
    """规则 3: MRN 相同 + 名字和 DOB 都相同 -> 复用现有 Patient。"""
    services.create_order(make_data())
    # 同 MRN 同名同 DOB, 换不同药避免 Order 重复。
    services.create_order(make_data(medication="Enbrel"))
    assert Patient.objects.count() == 1


def test_patient_same_mrn_different_identity_warns():
    """规则 4: MRN 相同 + 名字或 DOB 不同 -> DuplicateWarningException。"""
    services.create_order(make_data())
    with pytest.raises(DuplicateWarningException):
        # 同 MRN, 但名字不同。
        services.create_order(make_data(first_name="Bob"))


def test_patient_same_identity_different_mrn_warns():
    """规则 5: 名字+DOB 相同 + MRN 不同 -> DuplicateWarningException。"""
    services.create_order(make_data())
    with pytest.raises(DuplicateWarningException):
        # 同名同 DOB, 但换了一个 MRN。
        services.create_order(make_data(mrn="999999"))


# ---------------------------------------------------------------------------
# Order 规则
# ---------------------------------------------------------------------------
def test_order_same_patient_med_same_day_blocks():
    """规则 6: 同患者 + 同药 + 同一天 -> DuplicateBlockedException。"""
    services.create_order(make_data())
    with pytest.raises(DuplicateBlockedException):
        # 同患者 (同 MRN/名/DOB) + 同药 + 今天 -> 重复下单。
        services.create_order(make_data())


def test_order_same_patient_med_different_day_warns_and_confirm_bypasses():
    """规则 7: 同患者 + 同药 + 不同天 -> DuplicateWarningException; confirm=True 跳过。"""
    care_plan = services.create_order(make_data())

    # 把首单的 created_at 挪到昨天 (update() 绕过 auto_now_add)。
    yesterday = timezone.now() - timedelta(days=1)
    Order.objects.filter(pk=care_plan.order_id).update(created_at=yesterday)

    # 不带 confirm: 历史上同患者同药下过单 -> 警告。
    with pytest.raises(DuplicateWarningException):
        services.create_order(make_data())

    # 带 confirm=True: 跳过警告, 正常新建第二单。
    services.create_order(make_data(), confirm=True)
    assert Order.objects.count() == 2
