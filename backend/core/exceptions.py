"""统一错误处理的异常类 (Day 8)。

设计思想照搬课程参考仓库, 但机制换成纯 Django middleware (见 core/middleware.py),
因此这些异常 **不继承 DRF 的 APIException**, 只是普通 Python Exception 子类。

约定: 每个异常自带 http_status / type / code, middleware 直接读这几个属性拼出
统一的 JSON 响应。view / service 只管 raise, 不关心返回格式; 要改格式只改 middleware
一个地方。

故意不要 BaseAppException 基类 (参考仓库也没有): 这几个异常彼此独立, 共享属性靠
约定而非继承, 省掉一层抽象。
"""


class DuplicateBlockedException(Exception):
    """硬阻止: 业务规则不允许的重复 (如同一 NPI 对应不同 Provider、当天重复下单)。

    HTTP 409 Conflict —— 请求与现有资源冲突, 无论如何都不能继续。
    """

    http_status = 409
    type = "block"
    code = "DUPLICATE_BLOCKED"

    def __init__(self, message, detail=None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class DuplicateWarningException(Exception):
    """软警告: 疑似重复 (如疑似同一患者), 用户带 confirm=True 重发即可放行。

    HTTP 409 Conflict —— 与参考仓库一致: 未确认前订单尚未创建, 不是 "成功",
    所以用 409 而不是 200。响应里带 warnings 列表 + requires_confirmation=True,
    前端据此弹确认框。
    """

    http_status = 409
    type = "warning"
    code = "DUPLICATE_WARNING"

    def __init__(self, message, warnings=None, detail=None):
        self.message = message
        # warnings 是给前端逐条展示的提示列表; 不传就用 message 兜底。
        self.warnings = warnings if warnings is not None else [message]
        self.detail = detail
        super().__init__(message)
