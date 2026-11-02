"""LLM 工厂：根据配置创建客户端（委托 registry，provider 可插拔）。

导入本模块即默认注册 openai_compatible（见 llm/registry.py），
create_llm() 签名与行为保持不变（零破坏）。
"""
from .base import LLMClient
from .registry import create_llm, register_provider, unregister_provider

__all__ = ["create_llm", "register_provider", "unregister_provider", "LLMClient"]
