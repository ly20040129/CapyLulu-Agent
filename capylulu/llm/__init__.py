"""LLM 工厂：根据配置创建客户端"""
from ..config import config
from .base import LLMClient
from .client import OpenAICompatibleClient


def create_llm() -> LLMClient:
    """按 config.yaml 当前厂商创建客户端。"""
    cfg = config.llm_config
    return OpenAICompatibleClient(
        api_key=cfg.get("api_key", ""),
        base_url=cfg.get("base_url", ""),
        model=cfg.get("model", ""),
    )
