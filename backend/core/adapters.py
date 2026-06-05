"""core/adapters.py — 数据接入层抽象基类 (BaseIntakeAdapter)。

每个外部数据源 (诊所 JSON、药企 XML、…) 写一个 BaseIntakeAdapter 子类, 负责把
"它自己的格式" 翻译成统一的 InternalOrder。业务逻辑只认 InternalOrder, 永远不
直接碰原始数据 —— 加一个新来源 = 加一个 Adapter, 不动业务代码。

三步约定 (子类必须实现):
    parse()      原始数据 (bytes / str / dict) -> 结构化的中间产物 (parsed)
    transform()  parsed -> InternalOrder
    validate()   校验 InternalOrder, 不合格就 raise

Step 1: 这里只定义"接口长什么样"——纯抽象, 不写任何具体来源的实现。
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from .schemas import (
    InternalDiagnosis,
    InternalMedication,
    InternalOrder,
    InternalPatient,
    InternalProvider,
)


class BaseIntakeAdapter(ABC):
    """所有接入 Adapter 的基类。

    用法约定: 构造时传入原始数据, 子类实现 parse / transform / validate 三个钩子。
    (怎么把三步串起来, 等 Step 3 写完具体 Adapter 再看要不要抽编排, 现在不写 —— YAGNI。)

    为什么是"先 parse 再 transform 再 validate"三段而不是一个大函数:
      - parse  只关心"怎么把原始字节/字符串读成结构" (XML 解析、JSON 反序列化…),
               不关心字段语义;
      - transform 只关心"字段怎么映射到 InternalOrder", 假定输入已是结构化产物;
      - validate  只关心"翻译出来的 InternalOrder 业务上是否成立"。
    三者职责单一, 子类可以单独测试、单独替换。
    """

    #: 来源系统标识, 子类覆盖 (写进 InternalOrder.source, 便于审计 / 排查)。
    source: str | None = None

    def __init__(self, raw: Any) -> None:
        #: 外部传入的原始数据, 形态由具体来源决定 (bytes / str / dict / file-like)。
        self.raw = raw

    @abstractmethod
    def parse(self) -> Any:
        """把 self.raw 解析成结构化的中间产物 (通常是 dict / 已解析的 XML 树)。

        只做"读取与结构化", 不做字段映射、不做业务校验。
        解析失败 (格式损坏、非法编码…) 应在这里 raise。
        """
        ...

    @abstractmethod
    def transform(self, parsed: Any) -> InternalOrder:
        """把 parse() 的产物映射成 InternalOrder。

        只做字段搬运 / 改名 / 填默认值, 不做业务校验 (那是 validate 的事)。
        """
        ...

    @abstractmethod
    def validate(self, order: InternalOrder) -> None:
        """校验翻译后的 InternalOrder; 不合格就 raise, 合格则正常返回 (None)。

        校验"业务规则" (必填字段缺失、ICD-10 格式、NPI 位数…), 而非"解析能否成功"。
        """
        ...


class ClinicBAdapter(BaseIntakeAdapter):
    """小型诊所 (DOWNTOWN_CLINIC) 的 JSON 接入。

    诊所直接发 JSON (反序列化后就是 dict), 字段用缩写 (pt / dx / rx / npi_num…),
    日期是 MM/DD/YYYY。这里把它翻成统一的 InternalOrder, 业务层就不必认这套缩写了。

    对照 services.create_order_from_clinic (Day 9 的过程式写法): 同样的映射逻辑,
    这里按 parse / transform / validate 三段拆开, 各段职责单一、可单独测试。
    原始 dict 由基类 __init__ 存进 self.raw, 排查问题时可回溯。
    """

    source = "clinic_b"

    # ICD-10: 一个字母 + 两位数字, 可选小数点后再跟若干数字/字母 (如 G70.00、E11.9)。
    _ICD10 = re.compile(r"^[A-Z][0-9]{2}(\.[0-9A-Z]+)?$")

    def parse(self) -> dict:
        """诊所给的已经是 dict, 基本 passthrough; 只做一层防御性检查。

        真正解析 (反序列化 JSON 文本) 发生在更外层 (view / 调用方); 到这里 self.raw
        理应已是 dict。这里只确认类型, 不动结构 —— 字段映射留给 transform。
        """
        if not isinstance(self.raw, dict):
            raise ValueError(
                "ClinicBAdapter expects a dict, got %s" % type(self.raw).__name__
            )
        return self.raw

    def transform(self, parsed: dict) -> InternalOrder:
        """把诊所缩写字段映射成嵌套 InternalOrder。只搬字段, 不做业务校验。"""
        pt = parsed["pt"]
        provider = parsed["provider"]
        dx = parsed["dx"]
        rx = parsed["rx"]

        patient = InternalPatient(
            first_name=pt["fname"],
            last_name=pt["lname"],
            mrn=pt["mrn"],
            # MM/DD/YYYY -> date; 解析失败 (空串 / 格式错) 让 ValueError 冒出去。
            dob=datetime.strptime(pt["dob"], "%m/%d/%Y").date(),
            middle_initial=pt.get("mi"),
            gender=pt.get("gender"),
        )
        internal_provider = InternalProvider(
            name=provider["name"],
            npi=provider["npi_num"],
        )
        medication = InternalMedication(
            name=rx["med_name"],
            ndc=rx.get("ndc"),
            dose=rx.get("dosage"),       # 诊所叫 dosage, 内部统一叫 dose
            frequency=rx.get("freq"),    # 诊所叫 freq, 内部统一叫 frequency
        )
        diagnosis = InternalDiagnosis(
            primary=dx["primary"],
            additional=list(dx.get("secondary", [])),
        )

        return InternalOrder(
            patient=patient,
            provider=internal_provider,
            medication=medication,
            diagnosis=diagnosis,
            medication_history=list(parsed.get("med_hx", [])),
            patient_records=parsed.get("clinical_notes", ""),
            source=self.source,          # 写明来源, 便于审计 / 排查
        )

    def validate(self, order: InternalOrder) -> None:
        """校验业务规则: NPI 十位、MRN 六位、ICD-10 格式 (primary + 每个 secondary)。

        不合格抛 ValueError (沿用 Day 9 create_order_from_clinic 的约定)。
        """
        npi = order.provider.npi
        if not (isinstance(npi, str) and npi.isdigit() and len(npi) == 10):
            raise ValueError("invalid NPI %r: must be a 10-digit numeric string" % (npi,))

        mrn = order.patient.mrn
        if not (isinstance(mrn, str) and mrn.isdigit() and len(mrn) == 6):
            raise ValueError("invalid MRN %r: must be a 6-digit numeric string" % (mrn,))

        if not self._ICD10.match(order.diagnosis.primary):
            raise ValueError(
                "invalid primary diagnosis ICD-10 %r" % (order.diagnosis.primary,)
            )
        for code in order.diagnosis.additional:
            if not self._ICD10.match(code):
                raise ValueError("invalid additional diagnosis ICD-10 %r" % (code,))


# ----------------------------------------------------------------------
# 工厂: source 字符串 -> Adapter 类。
#
# 新增数据源 = 写一个 BaseIntakeAdapter 子类 + 在这里登记一行, 业务代码
# (services / view) 完全不动 —— 它们只调 get_adapter(source), 永远不认识
# 任何具体 Adapter 类名。这就是 Open/Closed: 对扩展开放, 对修改封闭。
# ----------------------------------------------------------------------
_ADAPTERS: dict[str, type[BaseIntakeAdapter]] = {
    ClinicBAdapter.source: ClinicBAdapter,
    # 新来源在此登记, 例如:
    #   PharmaAdapter.source: PharmaAdapter,
}


def get_adapter(source: str) -> type[BaseIntakeAdapter]:
    """按来源标识返回对应的 Adapter 类 (不是实例)。

    调用方拿到类后自己 new: get_adapter("clinic_b")(raw)。
    未知来源抛 ValueError, 错误信息带上当前已注册的来源, 方便排查。
    """
    try:
        return _ADAPTERS[source]
    except KeyError:
        known = ", ".join(sorted(_ADAPTERS)) or "(none)"
        raise ValueError(
            "unknown source %r; registered sources: %s" % (source, known)
        )
