import json
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from anthropic import Anthropic

ORDERS = {}

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
    data = json.loads(request.body)

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

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    care_plan = message.content[0].text

    order_id = str(uuid.uuid4())
    ORDERS[order_id] = {
        "id": order_id,
        "patient": data,
        "carePlan": care_plan,
        "status": "completed",
    }
    return JsonResponse(ORDERS[order_id])
