"""统一异常处理中间件 (Day 8)。

参考仓库用的是 DRF 的 EXCEPTION_HANDLER, 但 DRF 的 handler 只对走 DRF dispatch
的视图生效, 我们现在是纯 Django 函数视图。所以这里用 Django 原生的
`process_exception` 钩子达到同样的效果:

  - view / service 里只管 raise 语义化异常;
  - 任意视图抛出异常都会冒泡到这里, 由这一个地方统一转成 JSON;
  - 要改返回格式 → 只改这个文件。

以后真要引入 DRF, 这套 middleware 仍然兼容 (DRF 视图抛的 ValidationError 也会
被这里的兼容分支接住), 不用改。
"""
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import JsonResponse

from core.exceptions import DuplicateBlockedException, DuplicateWarningException

logger = logging.getLogger(__name__)


class ExceptionHandlerMiddleware:
    """把自定义异常 (以及 Django/DRF 的 ValidationError) 统一转成 JSON 响应。

    统一格式: {code, type, message, ...}
    认不出来的异常 return None, 原样交还给 Django 默认处理 (DEBUG 下出黄页,
    生产环境出 500), 不越权吞掉别人的异常。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 正常请求直接放行, 异常处理走 process_exception 钩子。
        return self.get_response(request)

    def process_exception(self, request, exception):
        # 1) 业务阻止 -> 409
        if isinstance(exception, DuplicateBlockedException):
            logger.warning("blocked: %s", exception.message)
            return JsonResponse(
                {
                    "code": exception.code,
                    "type": exception.type,
                    "message": exception.message,
                    "warnings": [],
                },
                status=exception.http_status,
            )

        # 2) 业务警告 -> 409 + requires_confirmation, 前端带 confirm 重发
        if isinstance(exception, DuplicateWarningException):
            logger.info("warning: %s", exception.message)
            return JsonResponse(
                {
                    "code": exception.code,
                    "type": exception.type,
                    "message": exception.message,
                    "warnings": exception.warnings,
                    "requires_confirmation": True,
                },
                status=exception.http_status,
            )

        # 3) Django 内置 ValidationError -> 400
        if isinstance(exception, DjangoValidationError):
            details = (
                exception.messages
                if hasattr(exception, "messages")
                else [str(exception)]
            )
            logger.warning("validation error: %s", details)
            return JsonResponse(
                {
                    "code": "VALIDATION_ERROR",
                    "type": "validation",
                    "message": "Validation failed",
                    "details": details,
                },
                status=400,
            )

        # 4) DRF 的 ValidationError 兼容分支 (现在没装 DRF 时这段是惰性的,
        #    以后装了 DRF, serializer 抛的 ValidationError 也会被接住)。
        try:
            from rest_framework.exceptions import ValidationError as DRFValidationError
        except ImportError:
            DRFValidationError = None
        if DRFValidationError is not None and isinstance(exception, DRFValidationError):
            logger.warning("DRF validation error: %s", exception.detail)
            return JsonResponse(
                {
                    "code": "VALIDATION_ERROR",
                    "type": "validation",
                    "message": "Validation failed",
                    "details": exception.detail,
                },
                status=400,
            )

        # 5) 其它异常: 不处理, 交还 Django 默认 (return None)。
        return None
