"""本地接收通道（httpin）。

通过 FastAPI 路由接收外部 POST 消息并写入收件箱，模拟 IM 服务器推送：
外部系统（测试脚本 / 模拟器）向 {base}/api/im/inbox/incoming 发 POST，
payload 形如 {"channel": "webhook", "text": "hello"}，
本通道把消息交给 broker 入队（inbox），并让 Leader 处理、经原通道回发。

本文件只定义通道实例（poll 语义：从收件箱出队待处理消息），
实际接收端点在 routers/im.py 中实现并复用 broker 的入队逻辑。
"""
from __future__ import annotations

from capylulu.im.broker import get_broker
from capylulu.im.channel import IMChannel, register_channel_type


class HttpInChannel(IMChannel):
    """本地接收通道：模拟 IM 服务器推送，消息落在收件箱。"""

    channel_type = "httpin"

    def __init__(self, name: str, enabled: bool = True):
        super().__init__(name, enabled)

    @classmethod
    def from_config(cls, cfg: dict) -> "HttpInChannel":
        return cls(cfg.get("name", ""), cfg.get("enabled", True))

    def send(self, text: str, **kwargs) -> dict:
        """把文本回发给外部（本地模拟：直接追加进收件箱的消息记录）。"""
        broker = get_broker()
        # 本地模拟回发：不真正外呼，仅记录回发日志供收件箱展示
        broker.record_reply(self.name, text)
        return {"ok": True, "message": "已模拟回发（本地通道）"}

    def poll(self) -> list[dict]:
        """主动拉取：httpin 消息由外部 POST 直接入队，无需主动拉取。"""
        return []

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["webhook_url"] = ""  # 占位，保持 schema 一致
        return d


register_channel_type("httpin", HttpInChannel)
