from django.urls import include, path
from . import views

urlpatterns = [
    path("api/orders/", views.create_order),
    path("api/orders/<int:order_id>", views.get_order),
    path("api/careplan/<int:care_plan_id>/status/", views.get_care_plan_status),
    # Prometheus 抓取端点 /metrics (放最后, 不影响上面的业务路由)
    path("", include("django_prometheus.urls")),
]
