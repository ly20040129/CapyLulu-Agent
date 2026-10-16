"""OpenAI 兼容客户端（智谱 GLM / DeepSeek 通用）"""
from openai import OpenAI
from .base import LLMClient


class OpenAICompatibleClient(LLMClient):
    """智谱和 DeepSeek 都走 OpenAI 兼容协议，一个实现通吃"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def chat(self, messages: list[dict], tools=None) -> dict:
        """发一轮 chat.completions，解析 content / tool_calls。"""
        kwargs = {"model": self._model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "",
                    },
                }
                for tc in msg.tool_calls
            ]
        return {"content": msg.content, "tool_calls": tool_calls}
