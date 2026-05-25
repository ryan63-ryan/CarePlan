from django.db import models


class Patient(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    # 需求文档 1.1: MRN 唯一, 6 位数字。存为字符串以保留前导零。
    mrn = models.CharField(max_length=6, unique=True)
    dob = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} (MRN {self.mrn})"


class Provider(models.Model):
    name = models.CharField(max_length=200)
    # 需求文档 1.1: NPI 10 位数字, 全国唯一标识。
    npi = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return f"{self.name} (NPI {self.npi})"


class Order(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="orders")
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="orders")
    medication = models.CharField(max_length=255)
    primary_diagnosis = models.CharField(max_length=20)  # ICD-10 code
    additional_diagnosis = models.JSONField(default=list, blank=True)  # list of ICD-10 codes
    medication_history = models.JSONField(default=list, blank=True)  # list of strings
    patient_records = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.pk}: {self.medication} for {self.patient}"


class CarePlan(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    # 需求文档 1.4: 一个 care plan 对应一个订单。
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="care_plan")
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CarePlan for Order #{self.order_id} ({self.status})"
