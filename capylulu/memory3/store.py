"""三级记忆存储：工作记忆 / 情景记忆 / 语义记忆。

目录结构（<data_dir>/memory/ 下，与既有单层 md 记忆共存，互不干扰）：
- working/   工作记忆：会话级上下文（working/<id>.json）
- episodic/  情景记忆：结构化事件记录（episodic/<id>.json）
- semantic/  语义记忆：蒸馏后的长期知识条目（semantic/<id>.json）

字段约定：
- 工作记忆：id / type / session / content / created_at / updated_at
- 情景记忆：id / type / time / task / action / result / agents / created_at
- 语义记忆：id / type / topic / points / sources / confidence / updated_at

全部为项目数据目录内的 JSON 文件，不触碰系统路径；提供 refresh_paths() 与
单层 memory.py 对齐，供数据目录迁移与隔离测试使用。
"""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

from ..config import config

MEMORY_DIR = config.data_dir / "memory"
TIERS = ("working", "episodic", "semantic")


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global MEMORY_DIR
    MEMORY_DIR = config.data_dir / "memory"


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_id(text: str) -> str:
    """清洗 id / 文件名：防路径遍历。"""
    text = (text or "").strip()
    text = re.sub(r'[\\/:*?"<>|\r\n]+', "_", text)
    return text[:80]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def _tier_dir(tier: str) -> Path:
    tier = tier if tier in TIERS else "working"
    d = MEMORY_DIR / tier
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_item(tier: str, item_id: str) -> dict | None:
    p = _tier_dir(tier) / f"{_safe_id(item_id)}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _write_item(tier: str, item: dict) -> None:
    p = _tier_dir(tier) / f"{_safe_id(item['id'])}.json"
    p.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- 工作记忆（会话级上下文） ----------------

def log_working(session: str = "default", content: str = "") -> dict:
    """写入/追加一条工作记忆；同会话自动合并到最新一条，返回 {id, session, merged}。"""
    content = (content or "").strip()
    session = _safe_id(session or "default") or "default"
    ts = now_str()
    for it in list_tier("working"):
        if it.get("session") == session:
            merged = (it.get("content", "") + "\n" + content).strip()
            it["content"] = merged
            it["updated_at"] = ts
            _write_item("working", it)
            return {"id": it["id"], "session": session, "merged": True, "updated_at": ts}
    item = {
        "id": _new_id("wk"),
        "type": "working",
        "session": session,
        "content": content,
        "created_at": ts,
        "updated_at": ts,
    }
    _write_item("working", item)
    return {"id": item["id"], "session": session, "merged": False, "updated_at": ts}


# ---------------- 情景记忆（结构化事件） ----------------

def log_episodic(task: str = "", action: str = "", result: str = "",
                 agents: str = "", event_time: str = "") -> dict:
    """记录一条情景事件（时间/任务/动作/结果/参与Agent）。event_time 留空取当前时间。"""
    ts = (event_time or "").strip() or now_str()
    item = {
        "id": _new_id("ep"),
        "type": "episodic",
        "time": ts,
        "task": (task or "").strip(),
        "action": (action or "").strip(),
        "result": (result or "").strip(),
        "agents": (agents or "").strip(),
        "created_at": now_str(),
    }
    _write_item("episodic", item)
    return {"id": item["id"], "time": ts}


# ---------------- 语义记忆（蒸馏后的长期知识） ----------------

def save_semantic(topic: str, points: list[str] | None = None,
                  sources: list[str] | str | None = None,
                  confidence: float = 0.7) -> dict:
    """写入/合并一条语义记忆。同主题合并：要点去重、来源并集、置信度取较大值、更新时间刷新。

    sources 支持 list[str] 或逗号分隔字符串。
    """
    topic = (topic or "").strip()
    if not topic:
        return {"id": "", "merged": False, "error": "主题不能为空"}
    if isinstance(sources, str):
        sources = [s for s in sources.split(",") if s.strip()]
    sources = [str(s).strip() for s in (sources or []) if str(s).strip()]
    points = [str(p).strip() for p in (points or []) if str(p).strip()]
    confidence = max(0.0, min(1.0, float(confidence or 0.7)))
    ts = now_str()

    for it in list_tier("semantic"):
        if (it.get("topic") or "").strip() == topic:
            old_points = list(it.get("points", []))
            for p in points:
                if p not in old_points:
                    old_points.append(p)
            old_src = list(it.get("sources", []))
            for s in sources:
                if s not in old_src:
                    old_src.append(s)
            it["points"] = old_points
            it["sources"] = old_src
            it["confidence"] = max(float(it.get("confidence", 0)), confidence)
            it["updated_at"] = ts
            _write_item("semantic", it)
            return {"id": it["id"], "merged": True, "updated_at": ts}

    item = {
        "id": _new_id("sm"),
        "type": "semantic",
        "topic": topic,
        "points": points,
        "sources": sources,
        "confidence": confidence,
        "updated_at": ts,
    }
    _write_item("semantic", item)
    return {"id": item["id"], "merged": False, "updated_at": ts}


# ---------------- 通用 ----------------

def list_tier(tier: str) -> list[dict]:
    """列出某级全部条目，按（updated_at 或 created_at 或 time）倒序。"""
    tier = tier if tier in TIERS else "working"
    rows: list[dict] = []
    for p in _tier_dir(tier).glob("*.json"):
        try:
            rows.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            continue

    def _sort_key(r: dict) -> str:
        return r.get("updated_at") or r.get("created_at") or r.get("time") or ""

    rows.sort(key=_sort_key, reverse=True)
    return rows


def count_tier(tier: str) -> int:
    """某级条目数量。"""
    return len(list_tier(tier))


def get_item(tier: str, item_id: str) -> dict | None:
    """读取单条。"""
    return _read_item(tier, item_id)


def delete_item(tier: str, item_id: str) -> bool:
    """删除单条（仅项目数据目录内的 JSON）。"""
    p = _tier_dir(tier) / f"{_safe_id(item_id)}.json"
    if not p.exists() or not p.is_file():
        return False
    p.unlink()
    return True


def tiers_summary() -> dict:
    """三级条目数量总览。"""
    return {t: count_tier(t) for t in TIERS}
