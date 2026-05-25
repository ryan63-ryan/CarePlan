import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Patient, Provider, Order, CarePlan


def care_plan_text(medication, diagnosis):
    return f"""1. Problem list (Drug therapy problems)
- Patient requires {medication} for {diagnosis}; monitor for therapy-related problems.

2. Goals (SMART)
- Achieve symptom control within 8 weeks while avoiding adverse events.

3. Pharmacist interventions / plan
- Counsel patient on {medication} administration, adherence, and red-flag symptoms.

4. Monitoring plan & lab schedule
- Baseline labs, then follow-up at weeks 4 and 12.
"""


class Command(BaseCommand):
    help = "Seed the database with mock patients, providers, orders, and care plans."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing rows in the 4 tables before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            CarePlan.objects.all().delete()
            Order.objects.all().delete()
            Patient.objects.all().delete()
            Provider.objects.all().delete()
            self.stdout.write(self.style.WARNING("Existing rows deleted (--reset)."))

        # --- Providers (NPI is the unique natural key) ---
        carter, _ = Provider.objects.get_or_create(
            npi="1234567890", defaults={"name": "Dr. Emily Carter"}
        )
        lee, _ = Provider.objects.get_or_create(
            npi="9876543210", defaults={"name": "Dr. Robert Lee"}
        )

        # --- Patients (MRN is the unique natural key) ---
        # 张三: 这个病人故意安排了多个 order, 用来在 TablePlus 里验证
        # "一个病人 -> 多个订单, 病人信息只存一行" 的外键关系。
        zhang, _ = Patient.objects.get_or_create(
            mrn="100001",
            defaults={
                "first_name": "San",
                "last_name": "Zhang",
                "dob": datetime.date(1975, 3, 12),
            },
        )
        maria, _ = Patient.objects.get_or_create(
            mrn="100002",
            defaults={
                "first_name": "Maria",
                "last_name": "Garcia",
                "dob": datetime.date(1982, 7, 30),
            },
        )
        james, _ = Patient.objects.get_or_create(
            mrn="100003",
            defaults={
                "first_name": "James",
                "last_name": "Smith",
                "dob": datetime.date(1968, 11, 5),
            },
        )

        # --- Orders ---
        # (patient, provider, medication, primary_dx, additional_dx, med_history)
        order_specs = [
            # 张三 的 3 个订单, 都指向同一个 patient_id, 但是 3 行独立的 order
            (zhang, carter, "IVIG (Immune Globulin)", "G70.00",
             ["E11.9"], ["Pyridostigmine 60mg", "Prednisone 10mg"]),
            (zhang, carter, "Prednisone", "G70.00",
             [], ["Pyridostigmine 60mg"]),
            (zhang, lee, "Pyridostigmine", "G70.00",
             [], []),
            # 其他病人各 1 个订单
            (maria, lee, "Adalimumab", "M05.79",
             ["K50.90"], ["Methotrexate 15mg"]),
            (james, carter, "Apixaban", "I48.91",
             ["I10"], ["Metoprolol 50mg", "Atorvastatin 20mg"]),
        ]

        created_orders = 0
        for patient, provider, medication, dx, add_dx, med_hist in order_specs:
            order, created = Order.objects.get_or_create(
                patient=patient,
                provider=provider,
                medication=medication,
                defaults={
                    "primary_diagnosis": dx,
                    "additional_diagnosis": add_dx,
                    "medication_history": med_hist,
                    "patient_records": f"Mock records for {patient.first_name} {patient.last_name}.",
                },
            )
            if created:
                created_orders += 1
            # 每个 order 配一个 care plan
            CarePlan.objects.get_or_create(
                order=order,
                defaults={
                    "content": care_plan_text(medication, dx),
                    "status": CarePlan.Status.COMPLETED,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete: {Patient.objects.count()} patients, "
            f"{Provider.objects.count()} providers, "
            f"{Order.objects.count()} orders, "
            f"{CarePlan.objects.count()} care plans "
            f"({created_orders} new orders this run)."
        ))
        self.stdout.write(
            f"Patient 'San Zhang' (MRN 100001) has "
            f"{zhang.orders.count()} orders -> check core_order for 3 rows with the same patient_id."
        )
