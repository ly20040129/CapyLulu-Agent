"""自我改进：基于经验库生成改进建议并应用。

批次7「自主进化」的执行层：从经验库（lessons.py）取候选经验，评估每条建议——

- 低风险（自动应用）：向对应 Agent 的 prompt 追加一条注意项（或注入系统使用偏好），
  直接生效并记录 evolution_log；
- 高风险（仅记录）：写入 <data_dir>/evolve/evolution_log.json，标记 pending 待人工确认；
- 自动应用上限：每次最多应用 max_auto 条，防失控；
- LLM 不可用：规则降级决策（高置信度低风险直接应用，中置信度记录待确认，低置信度跳过）。
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from .. import agents_store
from ..config import config
from ..llm import create_llm
from . import lessons

EVOLUTION_LOG = config.data_dir / "evolve" / "evolution_log.json"
MAX_LOG = 500  # 进化日志上限，超出丢弃最旧
DEFAULT_MAX_AUTO = 3  # 单次自动应用上限


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global EVOLUTION_LOG
    EVOLUTION_LOG = config.data_dir / "evolve" / "evolution_log.json"


def _llm_ready() -> bool:
    return bool(config.llm_config.get("api_key"))


# ---------------- 进化日志 ----------------

def _load_log() -> list[dict]:
    if not EVOLUTION_LOG.exists():
        return []
    try:
        data = json.loads(EVOLUTION_LOG.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _save_log(items: list[dict]) -> None:
    EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    tmp = EVOLUTION_LOG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(EVOLUTION_LOG)


def _append_log(entry: dict) -> dict:
    items = _load_log()
    items.append(entry)
    if len(items) > MAX_LOG:
        items = items[-MAX_LOG:]
    _save_log(items)
    return entry


def list_log(limit: int = 100) -> list[dict]:
    """进化日志列表（新 → 旧）。"""
    if limit < 1 or limit > 500:
        limit = 100
    items = _load_log()
    return list(reversed(items[-limit:]))


def log_stats() -> dict:
    items = _load_log()
    by_status: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    for it in items:
        s = it.get("status", "?")
        r = it.get("risk", "?")
        by_status[s] = by_status.get(s, 0) + 1
        by_risk[r] = by_risk.get(r, 0) + 1
    return {"total": len(items), "by_status": by_status, "by_risk": by_risk}


# ---------------- LLM 评估 ----------------

def _build_prompt(lesson: dict) -> str:
    return (
        "你是自主进化改进引擎。根据以下经验库条目，判断是否值得应用为系统改进。\n"
        "输出 JSON："
        "{\"apply\": true或false, "
        "\"target\": \"agent\" 或 \"system\", "
        "\"agent_name\": \"要追加提示的Agent名(如 总代理/文件管家/电脑管家；target=system时留空)\", "
        "\"patch_text\": \"追加的注意项或使用偏好(一句话，20字以内)\", "
        "\"risk\": \"low\" 或 \"high\"}\n"
        "若建议清晰明确且改动小则 risk=low；涉及删除、覆盖、大改行为则 risk=high。"
        "只输出 JSON，不要解释。\n\n经验条目：\n"
        f"触发条件：{lesson.get('trigger', '')}\n建议：{lesson.get('advice', '')}\n"
        f"置信度：{lesson.get('confidence', 0.5)}"
    )


def _parse_json_object(text: str) -> dict | None:
    if not text:
        return None
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        start = text.index("{")
        end = text.rindex("}")
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _llm_eval(lesson: dict) -> dict | None:
    """LLM 评估一条经验；失败返回 None 以触发规则降级。"""
    try:
        llm = create_llm()
        resp = llm.chat([{"role": "user", "content": _build_prompt(lesson)}])
        return _parse_json_object(resp.get("content") or "")
    except Exception:  # noqa: BLE001
        return None


def _rule_eval(lesson: dict) -> dict:
    """规则降级决策：按置信度分档。"""
    conf = float(lesson.get("confidence", 0.5))
    advice = (lesson.get("advice") or "").strip()
    if conf >= 0.7 and len(advice) <= 60:
        return {
            "apply": True,
            "target": "agent",
            "agent_name": "总代理",
            "patch_text": advice[:30],
            "risk": "low",
        }
    if conf >= 0.4:
        return {
            "apply": True,
            "target": "system",
            "agent_name": "",
            "patch_text": advice[:30],
            "risk": "high",
        }
    return {"apply": False, "target": "system", "agent_name": "", "patch_text": "", "risk": "low"}


# ---------------- 应用 ----------------

def _apply_to_agent(agent_name: str, patch_text: str) -> tuple[bool, str]:
    """向指定 Agent 的 prompt 追加一条注意项；Agent 不存在返回失败。"""
    agent_name = (agent_name or "").strip() or "总代理"
    patch = (patch_text or "").strip()
    if not patch:
        return False, "改进内容为空"
    agents = agents_store.list_agents()
    target = next((a for a in agents if a.get("name") == agent_name), None)
    if target is None:
        return False, f"Agent「{agent_name}」不存在，跳过自动应用"
    old_prompt = target.get("prompt") or ""
    new_prompt = (old_prompt.rstrip() + f"\n\n【自主进化】{patch}") if old_prompt else f"【自主进化】{patch}"
    msg = agents_store.update_agent(agent_name, prompt=new_prompt)
    if msg:
        return False, msg
    return True, f"已向「{agent_name}」prompt 追加注意项"


def improve(max_auto: int = DEFAULT_MAX_AUTO, force: bool = False) -> dict:
    """基于经验库生成改进建议并应用，返回处理明细。

    - max_auto：单次自动应用上限（默认 3），高风险仅记录不计入上限；
    - force=False 时仅做校验（真正的间隔/任务数触发由 maybe_evolve 负责）。
    """
    if max_auto < 1 or max_auto > 20:
        max_auto = DEFAULT_MAX_AUTO
    all_lessons = lessons.list_lessons(limit=1000)
    # 候选：未应用的经验优先，其次置信度 >= 0.6；按置信度降序
    candidates = [
        it for it in all_lessons
        if not int(it.get("applied", 0)) or float(it.get("confidence", 0.5)) >= 0.6
    ]
    candidates.sort(key=lambda it: float(it.get("confidence", 0.5)), reverse=True)
    if not candidates:
        return {
            "considered": 0, "applied": 0, "high_risk": 0, "skipped": 0,
            "message": "经验库暂无候选经验可改进",
            "applied_items": [], "log_items": [],
        }

    applied = 0
    high_risk = 0
    skipped = 0
    applied_items: list[dict] = []
    log_items: list[dict] = []
    changed_agent = False

    for lesson in candidates:
        if applied >= max_auto:
            break
        decision = _llm_eval(lesson) if _llm_ready() else None
        if decision is None:
            decision = _rule_eval(lesson)

        if not decision.get("apply"):
            skipped += 1
            continue

        risk = str(decision.get("risk", "low"))
        patch_text = str(decision.get("patch_text", "")).strip()
        target_agent = str(decision.get("agent_name", "")).strip()
        log_entry = {
            "id": uuid.uuid4().hex[:8],
            "ts": lessons.now_str(),
            "lesson_id": lesson.get("id", ""),
            "trigger": (lesson.get("trigger") or "")[:200],
            "advice": (lesson.get("advice") or "")[:300],
            "suggestion": patch_text[:200],
            "risk": risk,
            "status": "pending" if risk == "high" else "applied",
            "note": "",
        }

        if risk == "high":
            # 高风险：仅记录，待人工确认
            log_entry["note"] = "高风险建议，已记录待人工确认"
            log_entry["target_agent"] = target_agent
            _append_log(log_entry)
            high_risk += 1
            log_items.append(log_entry)
            continue

        # 低风险：自动应用（向 Agent prompt 追加 或 注入系统偏好）
        if decision.get("target") == "system" or not target_agent:
            ok, note = _apply_to_agent("总代理", patch_text)
            target_agent = "总代理"
        else:
            ok, note = _apply_to_agent(target_agent, patch_text)
        if not ok:
            log_entry["status"] = "skipped"
            log_entry["note"] = note
            _append_log(log_entry)
            skipped += 1
            log_items.append(log_entry)
            continue

        changed_agent = True
        lessons.mark_applied(lesson.get("id", ""))
        applied += 1
        log_entry["status"] = "applied"
        log_entry["target_agent"] = target_agent
        log_entry["note"] = note
        _append_log(log_entry)
        applied_items.append({
            "lesson_id": lesson.get("id", ""),
            "trigger": (lesson.get("trigger") or "")[:120],
            "target_agent": target_agent,
            "suggestion": patch_text[:120],
            "risk": "low",
        })
        log_items.append(log_entry)

    if changed_agent:
        try:
            from ..ui.common import agent
            agent.reconfigure()
        except Exception:  # noqa: BLE001
            pass

    return {
        "considered": len(candidates[:max_auto * 2]),
        "applied": applied,
        "high_risk": high_risk,
        "skipped": skipped,
        "max_auto": max_auto,
        "message": f"评估 {len(candidates[:max_auto * 2])} 条候选，自动应用 {applied} 条，"
                   f"高风险记录 {high_risk} 条，跳过 {skipped} 条",
        "applied_items": applied_items,
        "log_items": log_items,
    }
