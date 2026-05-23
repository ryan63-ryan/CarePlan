from django.urls import path
from . import views

urlpatterns = [
    path("api/orders/", views.create_order),
]
