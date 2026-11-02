"""LLM 提供方注册表：provider 名 -> 工厂（工厂入参为配置 dict，返回 LLMClient）。

新增 provider 只需 register_provider("xxx", factory)，零改动核心；
create_llm() 缺省读 config.llm["provider"]，再缺省回退 "openai_compatible"。
"""
from __future__ import annotations

from typing import Callable

from ..config import config
from .base import LLMClient

PROVIDERS: dict[str, Callable[[dict], LLMClient]] = {}

DEFAULT_PROVIDER = "openai_compatible"


def register_provider(name: str, factory: Callable[[dict], LLMClient]) -> bool:
    """注册 provider 工厂；同名拒绝。"""
    if not name or name in PROVIDERS:
        return False
    PROVIDERS[name] = factory
    return True


def unregister_provider(name: str) -> bool:
    """注销 provider；返回是否真的移除。"""
    return PROVIDERS.pop(name, None) is not None


def _openai_compatible_factory(cfg: dict) -> LLMClient:
    """默认工厂：OpenAI 兼容协议（智谱 / DeepSeek / 任意兼容端点通吃）。"""
    from .client import OpenAICompatibleClient  # 延迟导入避免循环
    return OpenAICompatibleClient(
        api_key=cfg.get("api_key", ""),
        base_url=cfg.get("base_url", ""),
        model=cfg.get("model", ""),
    )


# 默认注册 openai_compatible（模块导入即生效，保持零破坏）
register_provider(DEFAULT_PROVIDER, _openai_compatible_factory)


def create_llm(provider: str | None = None) -> LLMClient:
    """按 provider 名创建客户端；缺省读 config.llm["provider"]，默认 openai_compatible。

    兼容旧配置：PROVIDERS 中无对应工厂（如旧 config 的 zhipu / deepseek）时，
    回退 openai_compatible 工厂——配置仍从 config.llm_config 读取，行为不变。
    """
    name = provider or config.llm.get("provider") or DEFAULT_PROVIDER
    factory = PROVIDERS.get(name) or PROVIDERS.get(DEFAULT_PROVIDER)
    if factory is None:
        raise RuntimeError("未注册任何 LLM provider，无法创建客户端")
    return factory(config.llm_config)
