"""core/schemas.py — 内部标准订单格式 (InternalOrder)。

所有外部数据源 (诊所 JSON、药企 XML、…) 先翻译成 InternalOrder, 业务逻辑
(create_order / care plan 生成) 只认这一种格式。

Step 1: 这里只定义"长什么样"——纯数据容器, 不做任何校验。
校验放哪里 (集中在 dataclass 还是各 Adapter) 留到 Step 3 再决定。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class InternalPatient:
    first_name: str
    last_name: str
    mrn: str
    dob: date | None = None
    # 选填: 来源里有、当前业务逻辑暂时不用的字段, 先留位 (不丢信息)。
    middle_initial: str | None = None
    gender: str | None = None


@dataclass(frozen=True)
class InternalProvider:
    name: str
    npi: str
    facility: str | None = None


@dataclass(frozen=True)
class InternalMedication:
    name: str
    ndc: str | None = None
    dose: str | None = None
    frequency: str | None = None


@dataclass(frozen=True)
class InternalDiagnosis:
    primary: str                                  # ICD-10
    additional: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InternalOrder:
    patient: InternalPatient
    provider: InternalProvider
    medication: InternalMedication
    diagnosis: InternalDiagnosis
    medication_history: list[str] = field(default_factory=list)
    patient_records: str = ""
    source: str | None = None                     # 来源系统标识, 便于审计 / 排查

    def to_create_order_data(self) -> dict:
        """适配现有 create_order(data): 摊平成它认识的扁平 dict。"""
        return {
            "first_name": self.patient.first_name,
            "last_name": self.patient.last_name,
            "mrn": self.patient.mrn,
            "dob": self.patient.dob,
            "provider_name": self.provider.name,
            "npi": self.provider.npi,
            "medication": self.medication.name,
            "primary_diagnosis": self.diagnosis.primary,
            "additional_diagnosis": self.diagnosis.additional,
            "medication_history": self.medication_history,
            "patient_records": self.patient_records,
        }
