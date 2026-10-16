"""钉钉 / 企业微信机器人 Webhook 通道。

通过群机器人 Webhook URL 发送文本消息：
- 钉钉：POST {webhook_url}，JSON {"msgtype": "text", "text": {"content": text}}
- 企业微信：POST {webhook_url}，JSON {"msgtype": "text", "text": {"content": text}}

钉钉机器人在安全设置中开启「加签」时，需要在请求 URL 上追加
timestamp 与 sign 两个查询参数（sign 用机器人密钥按官方算法生成），
否则钉钉返回「机器人发送签名不匹配」。
官方签名算法：
    timestamp = 毫秒级时间戳（字符串）
    string_to_sign = f"{timestamp}\n{secret}"
    sign = base64(HMAC-SHA256(key=secret, msg=string_to_sign)) 并做 URL 编码

两者发送格式一致，仅在返回体字段上略有差异，统一按 {"ok": bool, "message": str} 返回。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from capylulu.im.channel import IMChannel, register_channel_type

_TIMEOUT = 10  # 秒


class WebhookChannel(IMChannel):
    """标准机器人 Webhook 通道（钉钉 / 企业微信通用）。

    secret 仅对钉钉生效：非空时发送会自动带上官方加签参数。
    """

    channel_type = "webhook"

    def __init__(self, name: str, webhook_url: str = "", enabled: bool = True,
                 secret: str = ""):
        super().__init__(name, enabled)
        self.webhook_url = webhook_url or ""
        self.secret = (secret or "").strip()

    @classmethod
    def from_config(cls, cfg: dict) -> "WebhookChannel":
        return cls(
            cfg.get("name", ""),
            cfg.get("webhook_url", ""),
            cfg.get("enabled", True),
            cfg.get("secret", ""),
        )

    def _signed_url(self) -> str:
        """钉钉加签：在 webhook_url 上追加 timestamp 与 sign 查询参数。"""
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode("utf-8")
        string_to_sign = f"{timestamp}\n{self.secret}".encode("utf-8")
        hmac_code = hmac.new(secret_enc, string_to_sign, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        sep = "&" if "?" in self.webhook_url else "?"
        return f"{self.webhook_url}{sep}timestamp={timestamp}&sign={sign}"

    def send(self, text: str, **kwargs) -> dict:
        if not text:
            return {"ok": False, "message": "消息内容为空"}
        if not self.webhook_url:
            return {"ok": False, "message": "缺少 webhook_url"}
        payload = {"msgtype": "text", "text": {"content": str(text)}}
        data = json.dumps(payload).encode("utf-8")
        url = self._signed_url() if self.secret else self.webhook_url
        req = urllib.request.Request(
            url,
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
        if self.secret:
            d["secret"] = self.secret
        return d


register_channel_type("webhook", WebhookChannel)
