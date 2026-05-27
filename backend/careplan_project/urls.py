from django.urls import path
from . import views

urlpatterns = [
    path("api/orders/", views.create_order),
    path("api/orders/<int:order_id>", views.get_order),
    path("api/careplan/<int:care_plan_id>/status/", views.get_care_plan_status),
]
