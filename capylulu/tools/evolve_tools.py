"""自主进化工具：经验库管理 / 触发反思 / 触发改进（注册进主 registry）。"""
from __future__ import annotations

from ..evolve import improve, lessons, maybe, reflect
from .registry import tool


@tool(
    name="evolve_lesson",
    description=(
        "管理自主进化经验库（data/evolve/lessons.json）。支持三种动作："
        "list（列出经验库条目与统计）、add（新增经验：trigger 触发条件 + advice 建议 + "
        "task_ref 来源任务 + confidence 置信度0~1）、remove（按 lesson_id 删除经验）。"
        "用于沉淀成功做法与失败教训，供后续自我改进复用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "操作：list / add / remove",
                "enum": ["list", "add", "remove"],
            },
            "trigger": {"type": "string", "description": "触发条件（add 时必填）"},
            "advice": {"type": "string", "description": "建议内容（add 时必填）"},
            "task_ref": {"type": "string", "description": "来源任务引用（add 可选）"},
            "confidence": {"type": "number", "description": "置信度 0~1（add 可选，默认 0.5）"},
            "lesson_id": {"type": "string", "description": "经验 ID（remove 时必填）"},
        },
        "required": ["action"],
    },
    risk="low",
)
def evolve_lesson(action: str = "list", trigger: str = "", advice: str = "",
                  task_ref: str = "", confidence: float = 0.5,
                  lesson_id: str = "") -> str:
    action = (action or "list").strip().lower()
    try:
        if action == "list":
            items = lessons.list_lessons(100)
            st = lessons.stats()
            if not items:
                return "经验库为空。可先触发反思（evolve_reflect）从任务台账沉淀经验。"
            lines = [f"经验库共 {st['total']} 条（已应用 {st['applied_total']} 次，平均置信度 {st['avg_confidence']}）："]
            for it in items:
                lines.append(
                    f"- [{it['id']}] {it.get('trigger', '')} → {it.get('advice', '')}"
                    f"（置信度 {it.get('confidence', 0.5)}，已应用 {it.get('applied', 0)} 次，{it.get('created_at', '')}）"
                )
            return "\n".join(lines)
        if action == "add":
            if not (trigger or "").strip() or not (advice or "").strip():
                return "add 需要提供 trigger 与 advice。"
            r = lessons.add_lesson(trigger, advice, task_ref, confidence)
            if r.get("duplicate"):
                return f"已存在相同经验（{r['lesson']['id']}），跳过以避免重复条目。"
            return f"✓ 经验已入库：{r['lesson']['id']}（{r['lesson']['created_at']}）"
        if action == "remove":
            if not lesson_id:
                return "remove 需要提供 lesson_id。"
            ok = lessons.remove_lesson(lesson_id)
            return f"✓ 已删除经验 {lesson_id}" if ok else f"未找到经验 {lesson_id}"
        return f"未知操作：{action}"
    except Exception as exc:  # noqa: BLE001
        return f"经验库操作失败：{exc}"


@tool(
    name="evolve_reflect",
    description=(
        "触发自主进化反思：从任务台账（capylulu/team 委派记录）最近完成/失败的任务批量反思，"
        "LLM 提炼成功经验与失败教训写入经验库（LLM 不可用时规则降级提取失败关键词模式）。"
        "force=true 无条件立即反思；force=false 时走 maybe_evolve 按间隔/新增任务数判定。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "force": {"type": "boolean", "description": "是否强制反思（默认 true）"},
            "limit": {"type": "integer", "description": "最多反思的台账任务数（默认 20）"},
            "interval_seconds": {"type": "integer", "description": "force=false 时自动触发间隔秒数（默认 3600）"},
            "min_new_tasks": {"type": "integer", "description": "force=false 时新增任务数阈值（默认 3）"},
        },
        "required": [],
    },
    risk="medium",
)
def evolve_reflect(force: bool = True, limit: int = 20,
                   interval_seconds: int = 3600, min_new_tasks: int = 3) -> str:
    try:
        if force:
            r = reflect.reflect(limit=int(limit or 20), force=True)
            return r.get("message", str(r))
        r = maybe.maybe_evolve(
            interval_seconds=int(interval_seconds or 3600),
            min_new_tasks=int(min_new_tasks or 3),
            limit=int(limit or 20),
            force=False,
        )
        if not r.get("triggered"):
            return f"未到触发时机：{r.get('reason', '')}"
        return r["reflect"].get("message", str(r["reflect"]))
    except Exception as exc:  # noqa: BLE001
        return f"自主进化反思失败：{exc}"


@tool(
    name="evolve_improve",
    description=(
        "触发自主进化改进：基于经验库生成改进建议，低风险建议自动应用"
        "（向对应 Agent 的 prompt 追加注意项或注入系统使用偏好），高风险建议仅记录到"
        "data/evolve/evolution_log.json 待人工确认。自动应用上限 max_auto 条防失控。"
        "force=true 无条件立即改进；force=false 时走 maybe_evolve 按间隔/新增任务数判定。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "force": {"type": "boolean", "description": "是否强制改进（默认 true）"},
            "max_auto": {"type": "integer", "description": "单次自动应用上限（默认 3，范围 1~20）"},
            "interval_seconds": {"type": "integer", "description": "force=false 时自动触发间隔秒数（默认 3600）"},
            "min_new_tasks": {"type": "integer", "description": "force=false 时新增任务数阈值（默认 3）"},
        },
        "required": [],
    },
    risk="medium",
)
def evolve_improve(force: bool = True, max_auto: int = 3,
                   interval_seconds: int = 3600, min_new_tasks: int = 3) -> str:
    try:
        if force:
            r = improve.improve(max_auto=int(max_auto or 3), force=True)
            return r.get("message", str(r))
        r = maybe.maybe_evolve(
            interval_seconds=int(interval_seconds or 3600),
            min_new_tasks=int(min_new_tasks or 3),
            max_auto=int(max_auto or 3),
            force=False,
        )
        if not r.get("triggered"):
            return f"未到触发时机：{r.get('reason', '')}"
        return r["improve"].get("message", str(r["improve"]))
    except Exception as exc:  # noqa: BLE001
        return f"自主进化改进失败：{exc}"
