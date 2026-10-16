"""LLM 客户端抽象基类"""
from abc import ABC, abstractmethod
from typing import Optional


class LLMClient(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], tools: Optional[list[dict]] = None) -> dict:
        """对话接口

        Args:
            messages: 消息列表 [{"role": ..., "content": ...}]
            tools: 工具定义（OpenAI function calling 格式）

        Returns:
            {"content": str | None, "tool_calls": list[dict] | None}
        """
        ...
