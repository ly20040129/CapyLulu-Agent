"""IM 通道抽象基类 + 通道注册表。

通道是 capylulu 与外部 IM 平台之间的消息管道：
- send(text)：把文本消息发往外部（webhook 推送 / 本地模拟回发）。
- poll()：主动拉取新消息（当前通道均无主动拉取能力，默认返回空）。
- close()：释放资源。

新增通道类型：实现 IMChannel 子类并用 register_channel_type() 注册即可。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar


class IMChannel(ABC):
    """通道基类。子类需实现 channel_type 与 send()。"""

    channel_type: ClassVar[str] = ""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name or ""
        self.enabled = bool(enabled)

    @classmethod
    def from_config(cls, cfg: dict) -> "IMChannel":
        """从配置字典构建通道实例（子类可覆写）。"""
        return cls(cfg.get("name", ""), cfg.get("enabled", True))

    @abstractmethod
    def send(self, text: str, **kwargs) -> dict:
        """发送文本消息。返回 {"ok": bool, "message": str}。"""

    def poll(self) -> list[dict]:
        """主动拉取新消息（默认无主动拉取能力）。"""
        return []

    def close(self) -> None:
        """释放资源（默认无操作）。"""

    def to_dict(self) -> dict:
        """导出配置字典（用于 data/im.json 持久化）。"""
        return {"name": self.name, "type": self.channel_type, "enabled": self.enabled}


# 通道注册表：channel_type -> 类
_REGISTRY: dict[str, type[IMChannel]] = {}


def register_channel_type(channel_type: str, cls: type[IMChannel]) -> type[IMChannel]:
    """注册通道类型（幂等）。"""
    _REGISTRY[channel_type] = cls
    return cls


def create_channel(cfg: dict) -> IMChannel | None:
    """按配置字典构建通道实例；未知类型返回 None。

    cfg 形如 {"name": "...", "type": "webhook|httpin", "webhook_url": "...", "enabled": true}
    """
    if not isinstance(cfg, dict):
        return None
    cls = _REGISTRY.get(str(cfg.get("type", "")))
    if cls is None:
        return None
    try:
        return cls.from_config(cfg)
    except Exception:  # noqa: BLE001
        return None


def registered_types() -> list[str]:
    """已注册的通道类型列表。"""
    return list(_REGISTRY.keys())
