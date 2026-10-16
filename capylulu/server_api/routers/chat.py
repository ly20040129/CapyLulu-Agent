"""对话与会话管理。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu import history as chatstore
from capylulu.ui.common import agent, _llm_ready

router = APIRouter(tags=["chat"])

OFFLINE_REPLY = "噜噜还没拿到 API Key 呢～点左侧「⚙️ 模型设置」填好 Key 再聊吧。"


def _public(sess: dict) -> dict:
    msgs = chatstore.normalize_messages(sess.get("messages", []))
    return {
        "id": sess.get("id"),
        "title": chatstore.title_of_id(sess.get("id", "")),
        "count": len(msgs),
        "created": sess.get("created", ""),
    }


@router.get("/chat/sessions")
def list_sessions() -> dict:
    sessions = chatstore.list_sessions()
    items = [_public(s) for s in sessions]
    items.reverse()  # 新的在前
    return {"items": items}


@router.post("/chat/sessions")
def create_session() -> dict:
    sess = chatstore.create_session()
    return _public(sess)


@router.get("/chat/sessions/{sess_id}")
def get_session(sess_id: str) -> dict:
    sess = chatstore.get_by_id(sess_id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        **_public(sess),
        "messages": chatstore.normalize_messages(sess.get("messages", [])),
    }


@router.post("/chat/sessions/{sess_id}/rename")
def rename_session(sess_id: str, body: dict) -> dict:
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    ok = chatstore.rename_by_id(sess_id, title)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True, "title": title}


@router.delete("/chat/sessions/{sess_id}")
def delete_session(sess_id: str) -> dict:
    ok = chatstore.delete_session(sess_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


class SendBody(BaseModel):
    session_id: str = ""
    text: str = ""
    specialist: str = "自动"


@router.post("/chat/send")
def send(body: SendBody) -> dict:
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="消息不能为空")

    prev: list = []
    if body.session_id:
        sess = chatstore.get_by_id(body.session_id)
        if sess:
            prev = chatstore.normalize_messages(sess.get("messages", []))

    history = prev + [{"role": "user", "content": text}]

    if not _llm_ready():
        reply = OFFLINE_REPLY
    else:
        try:
            reply = agent.run(text, prev, specialist=body.specialist or "自动")
        except Exception as exc:  # noqa: BLE001
            reply = f"噜噜这边卡了一下：{exc}\n\n可以点左侧「⚙️ 模型设置」确认 Key 与模型名，或再发一次试试。"

    reply = (reply or "").strip() or "噜噜没想好怎么回，你再说一次？"
    history = history + [{"role": "assistant", "content": reply}]

    sess_id = body.session_id
    if not sess_id:
        sess_id = chatstore.create_session()["id"]
    chatstore.upsert(sess_id, history)

    return {
        "session_id": sess_id,
        "reply": reply,
        "messages": history,
    }
