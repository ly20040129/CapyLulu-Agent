"""Self-Evolution 触发层：会话空闲 + 轮次阈值 → 独立 review 沉淀用户记忆。

批次7「自主进化」的用户记忆点火（仿 CowAgent Self-Evolution）：
- 会话 idle 超 10 分钟且消息数达阈值（默认 6 条 ≈ 3 个来回）时，后台触发独立 review；
- review 用同一 LLM 但动作受限：读取最近会话 → 提取用户偏好/事实/待办 → 写入用户记忆 md；
- 写入前对 data/memory/ 做快照备份（data/evolve/snapshots/），支持一键回滚；
- review 前后对比快照，有实际变更才更新状态并尝试系统通知（无变化不打扰）；
- 提取只增不改：与已有记忆同名的条目直接跳过，避免覆盖用户手动编辑的内容。

不引入调度框架，与 memory3.maybe_auto_dream / evolve.maybe 同风格（纯时间戳 + 计数判断）。
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from loguru import logger

from . import history as chatstore
from . import memory as memory_store
from .config import config
from .llm import create_llm

IDLE_SECONDS = 600          # 会话空闲阈值（10 分钟）
MIN_MESSAGES = 6            # 消息数阈值（约 3 个来回）
CHECK_INTERVAL = 60         # 后台检查间隔（秒）
SNAPSHOT_TTL = 72 * 3600    # 快照保留 72 小时
REVIEW_LIMIT = 20           # review 输入最近消息条数


def _state_file() -> Path:
    """会话活跃状态文件（动态取 data_dir，支持目录迁移）。"""
    return config.data_dir / "evolve" / ".self_evolve_state.json"


def _status_file() -> Path:
    """review 记录文件（供前端展示，保留最近 20 条）。"""
    return config.data_dir / "evolve" / "self_evolve_status.json"


def _snapshot_dir() -> Path:
    return config.data_dir / "evolve" / "snapshots"


def _llm_ready() -> bool:
    """是否已配置 API Key（与 ui.common._llm_ready 一致）。"""
    return bool(config.llm_config.get("api_key"))


# ---------------- 会话活跃状态 ----------------

def _read_state() -> dict:
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _write_state(state: dict) -> None:
    f = _state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_session_active(sess_id: str, message_count: int) -> None:
    """对话完成后登记会话活跃状态（chat.py 回调调用，供后台 idle 判断）。"""
    if not sess_id:
        return
    try:
        state = _read_state()
        sessions = state.setdefault("sessions", {})
        sessions[sess_id] = {
            "last_active": time.time(),
            "message_count": int(message_count or 0),
        }
        state["last_check"] = time.time()
        _write_state(state)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[SelfEvolve] 登记会话活跃状态失败：{exc}")


# ---------------- 快照（可回滚） ----------------

def _snapshot_key() -> dict[str, str]:
    """当前用户记忆文件 → 内容 hash（变更检测基准）。"""
    out: dict[str, str] = {}
    mem_dir = memory_store.MEMORY_DIR
    if not mem_dir.is_dir():
        return out
    for p in mem_dir.glob("*.md"):
        try:
            out[p.name] = hashlib.md5(
                p.read_text(encoding="utf-8").encode("utf-8")
            ).hexdigest()
        except Exception:  # noqa: BLE001
            continue
    return out


def _cleanup_snapshots() -> None:
    """清理超过保留期的快照，防止无限堆积。"""
    d = _snapshot_dir()
    if not d.is_dir():
        return
    now = time.time()
    for p in d.iterdir():
        if not p.is_dir():
            continue
        ts = p.stat().st_mtime  # 以目录修改时间判断过期，目录名日期不可转时间戳
        if now - ts > SNAPSHOT_TTL:
            try:
                shutil.rmtree(p, ignore_errors=True)
            except Exception:  # noqa: BLE001
                pass


def snapshot_backup(tag: str = "review") -> str:
    """把当前 data/memory/*.md 快照备份到 snapshots/<ts>_<tag>/，返回快照目录名。"""
    ts = time.strftime("%Y%m%d_%H%M%S")
    dest = _snapshot_dir() / f"{ts}_{tag}"
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    mem_dir = memory_store.MEMORY_DIR
    if mem_dir.is_dir():
        for p in mem_dir.glob("*.md"):
            try:
                shutil.copy2(p, dest / p.name)
                copied += 1
            except Exception:  # noqa: BLE001
                continue
    _cleanup_snapshots()
    logger.info(f"[SelfEvolve] 记忆快照已备份：{dest.name}（{copied} 条）")
    return dest.name


def restore_snapshot(name: str) -> str:
    """回滚到指定快照：把快照内 md 覆盖回 data/memory/。返回状态消息。"""
    src = _snapshot_dir() / (name or "")
    if not src.is_dir():
        return f"快照不存在：{name}"
    mem_dir = memory_store.MEMORY_DIR
    mem_dir.mkdir(parents=True, exist_ok=True)
    restored = 0
    for p in src.glob("*.md"):
        try:
            shutil.copy2(p, mem_dir / p.name)
            restored += 1
        except Exception:  # noqa: BLE001
            continue
    logger.info(f"[SelfEvolve] 已从快照回滚记忆：{name}（{restored} 条）")
    return f"✓ 已从快照 {name} 回滚 {restored} 条记忆"


def list_snapshots() -> list[str]:
    """快照目录列表（新 → 旧）。"""
    d = _snapshot_dir()
    if not d.is_dir():
        return []
    return sorted((p.name for p in d.iterdir() if p.is_dir()), reverse=True)


# ---------------- LLM 提取 ----------------

def _build_extract_prompt(messages: list[dict], existing_names: list[str]) -> str:
    lines = []
    for m in messages:
        role = "用户" if m.get("role") == "user" else "助手"
        lines.append(f"{role}：{(m.get('content') or '').strip()[:200]}")
    exist_txt = "；".join(existing_names) if existing_names else "（无）"
    return (
        "你是用户记忆提取引擎（Self-Evolution review）。请基于以下对话，提取值得长期记住的用户信息：\n"
        "1. 用户偏好（喜欢/不喜欢、习惯、风格倾向）\n"
        "2. 用户个人事实（身份、职业、正在做的项目、技术栈、所在地等稳定信息）\n"
        "3. 用户明确表达的待办/承诺（后续需要跟进的事）\n"
        "输出 JSON 数组，每项格式："
        "{\"name\": \"记忆标题(10字以内)\", \"content\": \"记忆内容(凝练事实，80字以内)\"}\n"
        "要求：只提取对话中新的、值得长期记住的信息，不要与已有记忆重复；"
        "没有值得记住的信息时输出 []。只输出 JSON，不要解释。\n\n"
        f"已有记忆标题：{exist_txt}\n\n对话记录：\n" + "\n".join(lines)
    )


def _parse_json_array(text: str) -> list[dict] | None:
    """容错解析 LLM 输出的 JSON 数组（支持 ```json 围栏与前后杂质文本）。"""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        start = text.index("[")
        end = text.rindex("]")
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, list) else None
    except Exception:  # noqa: BLE001
        return None


def _llm_extract(messages: list[dict], existing_names: list[str]) -> list[dict] | None:
    """LLM 提取用户记忆；任何失败返回 None（不降级写垃圾记忆）。"""
    try:
        llm = create_llm()
        resp = llm.chat([{"role": "user", "content": _build_extract_prompt(messages, existing_names)}])
        return _parse_json_array(resp.get("content") or "")
    except Exception:  # noqa: BLE001
        return None


# ---------------- 通知 ----------------

def _notify(title: str, message: str) -> None:
    """轻量系统通知（winotify toast，失败静默，不阻塞主流程）。"""
    try:
        from winotify import Notification

        Notification(
            app_id="Capylulu · 噜噜",
            title=title,
            msg=message,
            duration="short",
        ).show()
    except Exception:  # noqa: BLE001
        pass


def _write_status(entry: dict) -> None:
    """写入 review 记录（保留最近 20 条，供前端查询）。"""
    f = _status_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            data = []
    except Exception:  # noqa: BLE001
        data = []
    data.insert(0, entry)
    f.write_text(json.dumps(data[:20], ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- 独立 review ----------------

def _review_session(sess_id: str) -> dict:
    """对单个会话执行独立 review：提取用户记忆并落盘。返回报告 dict。"""
    sess = chatstore.get_by_id(sess_id)
    if not sess:
        return {"ok": False, "reason": "会话不存在", "added": 0, "skipped": 0}
    messages = chatstore.normalize_messages(sess.get("messages", []))
    if not messages:
        return {"ok": False, "reason": "会话无消息", "added": 0, "skipped": 0}
    msgs = messages[-REVIEW_LIMIT:]

    if not _llm_ready():
        return {"ok": False, "reason": "未配置 API Key，跳过自动提取", "added": 0, "skipped": 0}

    existing = [r["name"] for r in memory_store.list_memories()]
    items = _llm_extract(msgs, existing)
    if items is None:
        return {"ok": False, "reason": "LLM 提取失败", "added": 0, "skipped": 0}

    before = _snapshot_key()
    snap = snapshot_backup("review")
    added = 0
    skipped = 0
    added_names: list[str] = []
    for it in items:
        name = (it.get("name") or "").strip()
        content = (it.get("content") or "").strip()
        if not name or not content:
            continue
        if not name.endswith(".md"):
            name += ".md"
        # 只增不改：同名已存在（含用户手改）一律跳过，避免覆盖
        if (memory_store.MEMORY_DIR / name).exists():
            skipped += 1
            continue
        try:
            msg = memory_store.create_memory(name, content)
            if msg.startswith("✓"):
                added += 1
                added_names.append(name)
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[SelfEvolve] 记忆写入失败：{exc}")
            skipped += 1

    after = _snapshot_key()
    new_files = [k for k in after if k not in before]
    changed_files = [k for k in before if k in after and after[k] != before[k]]

    report = {
        "ok": True,
        "reason": "idle+轮次阈值触发",
        "added": added,
        "skipped": skipped,
        "added_names": added_names,
        "snapshot": snap,
        "new_files": new_files,
        "changed_files": changed_files,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_status(report)

    if added:
        _notify(
            "噜噜悄悄记下了新记忆",
            f"从最近对话沉淀 {added} 条用户记忆：{'、'.join(added_names[:5])}"
            + (" 等" if len(added_names) > 5 else "") + "（已自动快照，可回滚）",
        )
    return report


# ---------------- 触发入口 ----------------

def maybe_review(force: bool = False) -> dict:
    """后台调用：扫描活跃会话，满足 idle+轮次阈值 → 独立 review 沉淀用户记忆。

    - force=True 无条件 review 所有已登记会话（调试/手动触发）；
    - 处理完的会话从登记表移除，用户再次对话会重新登记（自然冷却）。
    """
    state = _read_state()
    sessions = state.get("sessions", {})
    now = time.time()
    due: list[tuple[str, dict]] = []
    for sid, rec in list(sessions.items()):
        idle = now - float(rec.get("last_active", 0) or 0)
        count = int(rec.get("message_count", 0))
        if force or (idle >= IDLE_SECONDS and count >= MIN_MESSAGES):
            due.append((sid, rec))
    scanned = len(sessions) + len(due) if not force else len(sessions)

    reviews: list[dict] = []
    for sid, rec in due:
        r = _review_session(sid)
        idle = now - float(rec.get("last_active", 0) or 0)
        r.update({
            "session_id": sid,
            "idle_seconds": int(idle),
            "message_count": int(rec.get("message_count", 0)),
        })
        reviews.append(r)
        sessions.pop(sid, None)

    state["sessions"] = sessions
    state["last_check"] = now
    _write_state(state)
    return {"scanned": scanned, "triggered": len(due), "reviews": reviews}


def status() -> dict:
    """当前触发状态（供前端展示）。"""
    state = _read_state()
    sessions = state.get("sessions", {})
    try:
        status_rows = json.loads(_status_file().read_text(encoding="utf-8")) or []
    except Exception:  # noqa: BLE001
        status_rows = []
    return {
        "active_sessions": len(sessions),
        "sessions": sessions,
        "idle_seconds": IDLE_SECONDS,
        "min_messages": MIN_MESSAGES,
        "last_check": state.get("last_check", 0),
        "snapshots": list_snapshots(),
        "recent_reviews": status_rows,
    }
