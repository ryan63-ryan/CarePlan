import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from anthropic import Anthropic

from core.models import Patient, Provider, Order, CarePlan

logger = logging.getLogger(__name__)

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


@csrf_exempt
@require_http_methods(["POST"])
def create_order(request):
    logger.info("received request")
    data = json.loads(request.body)
    logger.info(
        "parsed payload: patient=%s %s, medication=%s",
        data.get("firstName"),
        data.get("lastName"),
        data.get("medication"),
    )

    prompt = PROMPT_TEMPLATE.format(
        first_name=data.get("firstName", ""),
        last_name=data.get("lastName", ""),
        mrn=data.get("mrn", ""),
        provider=data.get("provider", ""),
        npi=data.get("npi", ""),
        diagnosis=data.get("diagnosis", ""),
        medication=data.get("medication", ""),
        additional_diagnosis=data.get("additionalDiagnosis", ""),
        medication_history=data.get("medicationHistory", ""),
        patient_records=data.get("patientRecords", ""),
    )

    logger.info("calling Anthropic API (prompt length=%d chars)...", len(prompt))
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    care_plan = message.content[0].text
    logger.info(
        "LLM returned: %d chars, stop_reason=%s, usage=%s",
        len(care_plan),
        message.stop_reason,
        message.usage,
    )

    # 按 MRN / NPI 复用已存在的病人 / 医生, 不重复创建。
    patient, _ = Patient.objects.get_or_create(
        mrn=data.get("mrn", ""),
        defaults={
            "first_name": data.get("firstName", ""),
            "last_name": data.get("lastName", ""),
        },
    )
    provider, _ = Provider.objects.get_or_create(
        npi=data.get("npi", ""),
        defaults={"name": data.get("provider", "")},
    )
    order = Order.objects.create(
        patient=patient,
        provider=provider,
        medication=data.get("medication", ""),
        primary_diagnosis=data.get("diagnosis", ""),
        additional_diagnosis=data.get("additionalDiagnosis", ""),
        medication_history=data.get("medicationHistory", ""),
        patient_records=data.get("patientRecords", ""),
    )
    care_plan_obj = CarePlan.objects.create(
        order=order,
        content=care_plan,
        status=CarePlan.Status.COMPLETED,
    )

    logger.info("stored order %s, returning response", order.id)
    return JsonResponse({
        "id": order.id,
        "patient": data,
        "carePlan": care_plan,
        "status": care_plan_obj.status,
    })


@require_http_methods(["GET"])
def get_order(request, order_id):
    order = Order.objects.select_related("patient", "provider", "care_plan").get(id=order_id)
    return JsonResponse({
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
    })
