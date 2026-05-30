import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.models import CarePlan
from core import serializers, services

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def create_order(request):
    logger.info("received request")
    data = json.loads(request.body)
    parsed = serializers.parse_order_input(data)
    confirm = data.get("confirm", False)
    try:
        care_plan = services.create_order(parsed, confirm=confirm)
    except services.DuplicateError as e:
        # 硬阻止: NPI 撞名 / 当天重复下单 -> 409 Conflict, key 用 "error"。
        return JsonResponse({"error": str(e)}, status=409)
    except services.DuplicateWarning as e:
        # 软警告: 疑似重复, 让前端带 confirm=true 再发一次。这里用 400 + "warning"。
        return JsonResponse(
            {"warning": str(e), "needs_confirm": True},
            status=400,
        )
    return JsonResponse(serializers.serialize_create_response(care_plan))


@require_http_methods(["GET"])
def get_care_plan_status(request, care_plan_id):
    # 前端轮询用: 拿 POST /api/orders/ 返回的 carePlanId 每隔几秒查一次状态。
    try:
        care_plan = services.get_care_plan(care_plan_id)
    except CarePlan.DoesNotExist:
        return JsonResponse({"error": "care plan not found"}, status=404)
    return JsonResponse(serializers.serialize_care_plan_status(care_plan))


@require_http_methods(["GET"])
def get_order(request, order_id):
    order = services.get_order(order_id)
    return JsonResponse(serializers.serialize_order(order))
