"""IM 通道包：通道抽象 + Webhook / 本地接收 + 消息中心。

- channel.py：IMChannel 抽象基类（send / poll / close）与通道注册表
- webhook.py：钉钉 / 企业微信机器人 Webhook 通道
- httpin.py：本地接收通道（模拟 IM 服务器推送，消息落收件箱）
- broker.py：消息中心（通道配置 + 收件箱 + 交给 Leader 处理回发）

导入本包即完成通道类型注册。
"""
from .channel import (
    IMChannel,
    create_channel,
    register_channel_type,
    registered_types,
)
from .webhook import WebhookChannel  # noqa: F401  (导入即注册)
from .httpin import HttpInChannel  # noqa: F401  (导入即注册)
from .broker import Broker, get_broker

__all__ = [
    "IMChannel",
    "WebhookChannel",
    "HttpInChannel",
    "Broker",
    "get_broker",
    "create_channel",
    "register_channel_type",
    "registered_types",
]
