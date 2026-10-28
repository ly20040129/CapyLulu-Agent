"""对话与会话管理。

- GET/POST /chat/sessions：会话列表 / 新建会话；
- GET/DELETE /chat/sessions/{id}：读取 / 删除会话；
- POST /chat/sessions/{id}/rename：重命名会话；
- POST /chat/send：发送消息（走 agent 链路）。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu import history as chatstore
from capylulu.ui.common import agent, _llm_ready

router = APIRouter(tags=["chat"])

OFFLINE_REPLY = "噜噜还没拿到 API Key 呢～点左侧「⚙️ 模型设置」填好 Key 再聊吧。"


def _public(sess: dict) -> dict:
    """会话公开摘要：id / 标题 / 消息数 / 创建时间。"""
    msgs = chatstore.normalize_messages(sess.get("messages", []))
    return {
        "id": sess.get("id"),
        "title": chatstore.title_of_id(sess.get("id", "")),
        "count": len(msgs),
        "created": sess.get("created", ""),
    }


@router.get("/chat/sessions")
def list_sessions() -> dict:
    """会话列表（新 → 旧）。

    注意：history.list_sessions() 返回的数据已按 updated 降序（新的在前），
    此处直接显式排序即可，严禁再 reverse（历史曾双重反转导致最新会话沉底）。
    """
    sessions = sorted(
        chatstore.list_sessions(),
        key=lambda s: s.get("updated") or 0,
        reverse=True,  # 新的在前
    )
    items = [_public(s) for s in sessions]
    return {"items": items}


@router.post("/chat/sessions")
def create_session() -> dict:
    """新建一个空会话。"""
    sess = chatstore.create_session()
    return _public(sess)


@router.get("/chat/sessions/{sess_id}")
def get_session(sess_id: str) -> dict:
    """按 id 读取会话完整消息。"""
    sess = chatstore.get_by_id(sess_id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        **_public(sess),
        "messages": chatstore.normalize_messages(sess.get("messages", [])),
    }


@router.post("/chat/sessions/{sess_id}/rename")
def rename_session(sess_id: str, body: dict) -> dict:
    """重命名会话标题。"""
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    ok = chatstore.rename_by_id(sess_id, title)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True, "title": title}


@router.delete("/chat/sessions/{sess_id}")
def delete_session(sess_id: str) -> dict:
    """删除会话。"""
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
    """发送消息并返回回复，消息落盘到会话。"""
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

    # 点火2-对话：每次对话完成后自动沉淀情景记忆（不影响主流程，失败静默）
    try:
        from capylulu.memory3 import store as m3_store
        who = body.specialist or "自动"
        m3_store.log_episodic(
            task=text,
            action="对话问答",
            result=(reply or "")[:300],
            agents=who if who != "自动" else "总代理",
        )
    except Exception:  # noqa: BLE001
        pass

    # 点火2-自进化：登记会话活跃状态，供后台 idle+轮次阈值触发用户记忆 review
    try:
        from capylulu import self_evolve
        self_evolve.mark_session_active(sess_id, len(history))
    except Exception:  # noqa: BLE001
        pass

    return {
        "session_id": sess_id,
        "reply": reply,
        "messages": history,
    }
