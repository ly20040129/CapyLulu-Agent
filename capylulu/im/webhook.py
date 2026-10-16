"""钉钉 / 企业微信机器人 Webhook 通道。

通过群机器人 Webhook URL 发送文本消息：
- 钉钉：POST {webhook_url}，JSON {"msgtype": "text", "text": {"content": text}}
- 企业微信：POST {webhook_url}，JSON {"msgtype": "text", "text": {"content": text}}

两者格式一致，仅在返回体字段上略有差异，统一按 {"ok": bool, "message": str} 返回。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from capylulu.im.channel import IMChannel, register_channel_type

_TIMEOUT = 10  # 秒


class WebhookChannel(IMChannel):
    """标准机器人 Webhook 通道（钉钉 / 企业微信通用）。"""

    channel_type = "webhook"

    def __init__(self, name: str, webhook_url: str = "", enabled: bool = True):
        super().__init__(name, enabled)
        self.webhook_url = webhook_url or ""

    @classmethod
    def from_config(cls, cfg: dict) -> "WebhookChannel":
        return cls(cfg.get("name", ""), cfg.get("webhook_url", ""), cfg.get("enabled", True))

    def send(self, text: str, **kwargs) -> dict:
        if not text:
            return {"ok": False, "message": "消息内容为空"}
        if not self.webhook_url:
            return {"ok": False, "message": "缺少 webhook_url"}
        payload = {"msgtype": "text", "text": {"content": str(text)}}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            result = json.loads(body)
        except urllib.error.HTTPError as e:
            return {"ok": False, "message": f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}"}
        except urllib.error.URLError as e:
            return {"ok": False, "message": f"网络错误: {e.reason}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"发送失败: {e}"}
        # 钉钉：{"errcode": 0, "errmsg": "ok"}；企业微信：{"errcode": 0, "errmsg": "ok"}
        errcode = result.get("errcode", 0)
        if errcode == 0:
            return {"ok": True, "message": "发送成功", "response": result}
        return {"ok": False, "message": result.get("errmsg", "发送失败") or "发送失败", "response": result}

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["webhook_url"] = self.webhook_url
        return d


register_channel_type("webhook", WebhookChannel)
