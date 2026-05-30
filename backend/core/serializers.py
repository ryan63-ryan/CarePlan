"""数据格式转换层: 前端格式 (camelCase) <-> 后端格式 (snake_case)。

只做字段映射 / 组装 dict, 不做任何校验和业务逻辑。
"""
from core.models import CarePlan


def parse_order_input(data):
    """前端 POST body -> 后端字段 dict。"""
    return {
        "mrn": data.get("mrn", ""),
        "first_name": data.get("firstName", ""),
        "last_name": data.get("lastName", ""),
        "npi": data.get("npi", ""),
        "provider_name": data.get("provider", ""),
        "medication": data.get("medication", ""),
        "primary_diagnosis": data.get("diagnosis", ""),
        "additional_diagnosis": data.get("additionalDiagnosis", ""),
        "medication_history": data.get("medicationHistory", ""),
        "patient_records": data.get("patientRecords", ""),
    }


def serialize_create_response(care_plan):
    """create_order 的响应体。"""
    return {
        "carePlanId": care_plan.id,
        "status": care_plan.status,
        "message": "received",
    }


def serialize_care_plan_status(care_plan):
    """轮询接口的响应体。只有 completed 才带正文。"""
    payload = {
        "carePlanId": care_plan.id,
        "status": care_plan.status,
    }
    if care_plan.status == CarePlan.Status.COMPLETED:
        payload["content"] = care_plan.content
    return payload


def serialize_order(order):
    """订单详情的响应体。"""
    return {
        "id": order.id,
        "patient": {
            "firstName": order.patient.first_name,
            "lastName": order.patient.last_name,
            "mrn": order.patient.mrn,
            "provider": order.provider.name,
            "npi": order.provider.npi,
            "diagnosis": order.primary_diagnosis,
            "medication": order.medication,
            "additionalDiagnosis": order.additional_diagnosis,
            "medicationHistory": order.medication_history,
            "patientRecords": order.patient_records,
        },
        "carePlan": order.care_plan.content,
        "status": order.care_plan.status,
    }
