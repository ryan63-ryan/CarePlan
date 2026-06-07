"""core/llm_services.py — LLM 服务抽象层 (BaseLLMService)。

把"调用某个大模型厂商拿文本"这件事抽象成统一接口: 业务代码只说"给你一段
prompt, 还我一段文本", 至于背后是 Anthropic 还是 OpenAI、用哪个 model、
max_tokens 多少、response 怎么剥壳 —— 全封在具体子类里, 业务层一概不知。

加一个新厂商 = 写一个 BaseLLMService 子类 + 在工厂登记一行, 业务代码不动。
跟 core/adapters.py 的接入层是同一套思路 (抽象基类 + source 工厂)。

Step 1: 只定义抽象 + 两个具体子类 + 工厂。还没接到 services / tasks —— 那是
下一步的事, 这里不碰其它文件。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from django.conf import settings


class BaseLLMService(ABC):
    """所有 LLM 服务的基类。

    唯一对外契约就是 generate(prompt) -> str: 输入一段提示词, 返回 LLM 生成的
    文本。厂商差异 (SDK、model、max_tokens、response 结构) 都藏在子类的 generate
    实现里, 调用方永远只关心"给提示拿文本"。
    """

    #: 厂商标识, 子类覆盖 (用于工厂登记 / 排查, 跟 adapters.py 的 source 同构)。
    source: str | None = None

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """返回 LLM 生成的文本。

        子类负责: 调用本厂商的 API (model / max_tokens 内部写死, 不暴露给业务),
        从厂商各自的 response 结构里把正文抽出来, 返回纯 str。
        """
        ...


class AnthropicService(BaseLLMService):
    """Anthropic (Claude) 实现。

    用 client.messages.create, 从 response.content[0].text 取正文。
    model / max_tokens 跟 tasks.py、run_worker.py 里现行的调用保持一致
    (claude-sonnet-4-6 / 2000), 这样将来接通时行为不变。
    """

    source = "anthropic"

    # 厂商细节, 业务代码不需要知道 —— 故意设成类常量封在这里。
    _MODEL = "claude-sonnet-4-6"
    _MAX_TOKENS = 2000

    def generate(self, prompt: str) -> str:
        # 惰性 import: 没装 anthropic 包时, 不至于 import 本模块就崩 —— 只有真正
        # 用到 Anthropic 时才要求这个依赖。
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=self._MODEL,
            max_tokens=self._MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        # Claude 把正文放在 content 列表第一个 block 的 .text。
        return message.content[0].text


class OpenAIService(BaseLLMService):
    """OpenAI (GPT) 实现。

    用 client.chat.completions.create, 从 response.choices[0].message.content
    取正文。response 结构跟 Anthropic 完全不同, 这正是要把它封在子类里的原因。
    """

    source = "openai"

    # 厂商细节, 业务代码不需要知道 —— 故意设成类常量封在这里。
    _MODEL = "gpt-4o-mini"   # 也可换 "gpt-4o", 改这一行即可, 业务层无感
    _MAX_TOKENS = 2000

    def generate(self, prompt: str) -> str:
        # 惰性 import: 没装 openai 包时不影响本模块被 import (此刻 requirements
        # 里还没有 openai, 这条很关键 —— 否则 import core.llm_services 直接崩)。
        from openai import OpenAI

        # OPENAI_API_KEY 暂时假定已在 settings 里; "key 不存在" 的处理留到
        # Feature Flag 那一节。这里直接读, 缺了让它自然报错。
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=self._MODEL,
            max_tokens=self._MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        # GPT 把正文放在 choices[0].message.content。
        return response.choices[0].message.content


# ----------------------------------------------------------------------
# 工厂: provider 字符串 -> LLM 服务实例。
#
# 用各子类的 .source 当 key (不写字面量), 跟 adapters.get_adapter 一致。
# 新增厂商 = 写一个 BaseLLMService 子类 + 在此登记一行, 业务代码不动。
# ----------------------------------------------------------------------
_LLM_SERVICES: dict[str, type[BaseLLMService]] = {
    AnthropicService.source: AnthropicService,
    OpenAIService.source: OpenAIService,
}


def get_llm_service(provider: str) -> BaseLLMService:
    """按厂商标识返回对应的 LLM 服务实例。

    与 get_adapter 不同: provider 不需要传原始数据, 直接 new 出来返回实例
    (调用方拿到就能 .generate)。未知 provider 抛 ValueError, 错误信息带上当前
    已注册的 providers, 方便排查。
    """
    try:
        service_cls = _LLM_SERVICES[provider]
    except KeyError:
        known = ", ".join(sorted(_LLM_SERVICES)) or "(none)"
        raise ValueError(
            "unknown LLM provider %r; registered providers: %s" % (provider, known)
        )
    return service_cls()
