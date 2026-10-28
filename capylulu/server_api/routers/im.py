"""IM 通道（批次9）：通道 CRUD / 发送测试 / 收件箱 / 外部接收端点。

- GET  /api/im/channels：通道列表；
- POST /api/im/channels：新增通道；
- PUT  /api/im/channels/{name}：更新通道；
- DELETE /api/im/channels/{name}：删除通道；
- POST /api/im/channels/{name}/test：发送测试消息；
- GET  /api/im/inbox：收件箱消息列表（含回复状态）；
- DELETE /api/im/inbox：清空收件箱；
- POST /api/im/inbox/incoming：外部消息接收（模拟 IM 服务器推送，入队并交 Leader 处理）；
- POST /api/im/poll：手动触发一次通道轮询 + 处理。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu.im import get_broker

router = APIRouter(tags=["im"])


# ---------------- 通道 CRUD ----------------

@router.get("/im/channels")
def list_channels() -> dict:
    """IM 通道列表（凭据脱敏后返回）。"""
    broker = get_broker()
    items = broker.config_list()
    # 凭据脱敏：secret（钉钉加签密钥等）绝不下发明文，仅标记是否已设置
    for it in items:
        it["has_secret"] = bool(it.get("secret"))
        it.pop("secret", None)
    return {"items": items, "types": ["webhook", "httpin"]}


class ChannelBody(BaseModel):
    name: str = ""
    type: str = "webhook"
    webhook_url: str = ""
    secret: str = ""
    enabled: bool = True


@router.post("/im/channels")
def add_channel(body: ChannelBody) -> dict:
    """新增 IM 通道。"""
    item = {"name": (body.name or "").strip(), "type": body.type,
            "webhook_url": body.webhook_url, "secret": (body.secret or "").strip(),
            "enabled": body.enabled}
    r = get_broker().add_channel(item)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("message", "新增失败"))
    return r


@router.put("/im/channels/{name}")
def update_channel(name: str, body: ChannelBody) -> dict:
    """更新 IM 通道配置。"""
    item = {"name": (body.name or "").strip(), "type": body.type,
            "webhook_url": body.webhook_url, "secret": (body.secret or "").strip(),
            "enabled": body.enabled}
    r = get_broker().update_channel(name, item)
    if not r.get("ok"):
        raise HTTPException(status_code=404, detail=r.get("message", "更新失败"))
    return r


@router.delete("/im/channels/{name}")
def delete_channel(name: str) -> dict:
    """删除 IM 通道。"""
    r = get_broker().delete_channel(name)
    if not r.get("ok"):
        raise HTTPException(status_code=404, detail=r.get("message", "删除失败"))
    return r


# ---------------- 发送测试 ----------------

class TestBody(BaseModel):
    text: str = "capylulu 通道测试：噜噜在吗？"


@router.post("/im/channels/{name}/test")
def send_test(name: str, body: TestBody) -> dict:
    """向指定通道发送一条测试消息。"""
    ch = get_broker().get_channel(name)
    if ch is None:
        raise HTTPException(status_code=404, detail=f"通道「{name}」不存在")
    try:
        return {"ok": True, "name": name, "result": ch.send(body.text or "capylulu 通道测试")}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"发送异常：{exc}") from exc


# ---------------- 收件箱 ----------------

@router.get("/im/inbox")
def list_inbox(limit: int = 100) -> dict:
    """收件箱消息列表（含回复状态）。"""
    return {"items": get_broker().list_inbox(limit)}


@router.delete("/im/inbox")
def clear_inbox() -> dict:
    """清空收件箱。"""
    n = get_broker().clear_inbox()
    return {"ok": True, "cleared": n, "message": f"已清空 {n} 条消息"}


# ---------------- 外部接收端点 ----------------

class IncomingBody(BaseModel):
    channel: str = "本地接收"
    text: str = ""


@router.post("/im/inbox/incoming")
def receive_incoming(body: IncomingBody) -> dict:
    """外部模拟 IM 服务器推送：入队并同步交给 Leader 处理、经原通道回发。"""
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    broker = get_broker()
    if broker.get_channel(body.channel) is None:
        # 允许未知通道名，默认落到「本地接收」
        body.channel = "本地接收"
    msg = broker.enqueue(body.channel, text)
    stats = broker.process_pending()
    return {"ok": True, "message": msg, "processed": stats.get("processed", 0),
            "failed": stats.get("failed", 0), "details": stats.get("details", [])}


# ---------------- 手动轮询 ----------------

@router.post("/im/poll")
def poll_channels() -> dict:
    """手动触发一次通道轮询 + 处理。"""
    return {"ok": True, **get_broker().poll_channels()}
