"""本地会话历史：<data_dir>/sessions.json（data_dir 由 config.yaml general.data_dir 决定，默认 data）"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from .config import config

STORE = config.data_dir / "sessions.json"


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global STORE, DATA_DIR
    STORE = config.data_dir / "sessions.json"
    DATA_DIR = STORE.parent


def _load() -> list[dict]:
    if not STORE.exists():
        return []
    try:
        return json.loads(STORE.read_text(encoding="utf-8")) or []
    except json.JSONDecodeError:
        return []


def _save(sessions: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")


def list_sessions() -> list[dict]:
    return _load()


def _display_titles(sessions: list[dict]) -> dict[str, str]:
    """会话 id → 下拉展示名：优先用首条用户消息（title），重名时加序号避免歧义。"""
    seen: dict[str, int] = {}
    out: dict[str, str] = {}
    for s in sessions:
        base = _title_of(s)
        seen[base] = seen.get(base, 0) + 1
        out[s["id"]] = base if seen[base] == 1 else f"{base} ({seen[base]})"
    return out


def title_of_id(sess_id: str) -> str:
    titles = _display_titles(_load())
    if sess_id in titles:
        return titles[sess_id]
    return "新对话"


DATA_DIR = STORE.parent


def _title_of(s: dict) -> str:
    t = (s.get("title") or "").strip()
    return t[:28] if t else "新对话"


def _clean_text(content) -> str:
    """把消息 content 归一化为字符串：兼容 Gradio 结构化 list/dict 与旧脏数据。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for it in content:
            if isinstance(it, dict) and it.get("text"):
                parts.append(str(it["text"]))
            elif it is not None:
                parts.append(str(it))
        return "\n".join(parts)
    if isinstance(content, dict):
        return str(content.get("text") or content.get("content") or "")
    if content is None:
        return ""
    return str(content)


def normalize_messages(messages) -> list:
    """清洗消息列表：只保留合法 dict 且 content 非空；content 统一为字符串。

    关键：Gradio Chatbot 组件值可能携带结构化 content（list/dict），
    直接写库或提取标题会崩溃（list 无 .replace），必须在此归一化。
    """
    out = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        content = _clean_text(m.get("content")).strip()
        if not content:
            continue
        m = dict(m)
        m["content"] = content
        out.append(m)
    return out


def _clean_session(s: dict) -> dict:
    out = dict(s)
    out["messages"] = normalize_messages(s.get("messages"))
    return out


def session_choices() -> list[tuple[str, str]]:
    """下拉选项：(显示名, 会话 id)。value 直接用 id，彻底规避重名序号竞态。"""
    items = [(label, sid) for sid, label in _display_titles(_load()).items()]
    return items or [("（暂无历史）", "")]


def get_by_choice(choice: str) -> dict | None:
    """按 id 或显示名取会话（优先 id）；返回清洗后的消息。"""
    if not choice or choice.startswith("（"):
        return None
    sessions = _load()
    for s in sessions:
        if s.get("id") == choice:
            return _clean_session(s)
    titles = _display_titles(sessions)
    for s in sessions:
        if titles.get(s["id"]) == choice:
            return _clean_session(s)
    return None


def create_session() -> dict:
    sess = {
        "id": uuid.uuid4().hex,
        "title": "新对话",
        "messages": [],
        "updated": time.time(),
    }
    sessions = _load()
    sessions.insert(0, sess)
    _save(sessions)
    return sess


def upsert(sess_id: str, messages: list, title: str | None = None) -> None:
    messages = normalize_messages(messages)
    sessions = _load()
    for s in sessions:
        if s["id"] == sess_id:
            s["messages"] = messages
            s["updated"] = time.time()
            if title:
                s["title"] = title[:40]
            elif messages and s.get("title") in ("新对话", None, ""):
                first = next((m["content"] for m in messages if m.get("role") == "user"), "")
                s["title"] = (first or "新对话").replace("\n", " ")[:28]
            break
    else:
        sessions.insert(0, {
            "id": sess_id,
            "title": (title or "新对话")[:40],
            "messages": messages,
            "updated": time.time(),
        })
    sessions.sort(key=lambda x: x.get("updated", 0), reverse=True)
    _save(sessions[:50])  # 最多留 50 个会话


def id_of_choice(choice: str) -> str | None:
    """下拉名称 → 会话 id。"""
    if not choice or choice.startswith("（"):
        return None
    titles = _display_titles(_load())
    for s in _load():
        if titles.get(s["id"]) == choice:
            return s["id"]
    return None


def delete_session(sess_id: str) -> bool:
    """按 id 删除会话并写回 sessions.json。"""
    sessions = _load()
    remained = [s for s in sessions if s.get("id") != sess_id]
    if len(remained) == len(sessions):
        return False
    _save(remained)
    return True


def delete_by_choice(choice: str) -> bool:
    """按下拉名称删除会话，成功返回 True。"""
    sess_id = id_of_choice(choice)
    if not sess_id:
        return False
    return delete_session(sess_id)


def rename_by_choice(choice: str, new_title: str) -> bool:
    """按下拉名称重命名会话（写回 sessions.json），成功返回 True。"""
    sess_id = id_of_choice(choice)
    if not sess_id:
        return False
    return rename_by_id(sess_id, new_title)


def get_by_id(sess_id: str) -> dict | None:
    """按 id 取会话（列表操作句柄用 id，规避重名序号竞态）；返回清洗后的消息。"""
    if not sess_id:
        return None
    for s in _load():
        if s.get("id") == sess_id:
            return _clean_session(s)
    return None


def rename_by_id(sess_id: str, new_title: str) -> bool:
    """按 id 重命名会话（写回 sessions.json），成功返回 True。"""
    if not sess_id:
        return False
    new_title = (new_title or "").strip()[:40]
    if not new_title:
        return False
    sessions = _load()
    for s in sessions:
        if s.get("id") == sess_id:
            s["title"] = new_title
            s["updated"] = time.time()
            break
    else:
        return False
    _save(sessions)
    return True
