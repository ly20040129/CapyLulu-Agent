"""三级记忆工具：记录情景事件 / 深度蒸馏 / 合并检索（注册进主 registry）。"""
from __future__ import annotations

from ..memory3 import dream, query as m3_query
from ..memory3 import store as m3_store
from .registry import tool


@tool(
    name="memory_log_event",
    description=(
        "记录一条情景记忆（结构化事件：时间/任务/动作/结果/参与Agent），"
        "写入 <data_dir>/memory/episodic/。用于把一次真实执行过程沉淀为可蒸馏的事件。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "任务名称或目标"},
            "action": {"type": "string", "description": "采取的动作（如：搜索文件 / 调用工具 xx）"},
            "result": {"type": "string", "description": "执行结果摘要"},
            "agents": {"type": "string", "description": "参与 Agent 名称（可逗号分隔多个）"},
            "time": {"type": "string", "description": "事件时间（YYYY-MM-DD HH:MM:SS，留空取当前时间）"},
        },
        "required": ["task", "action", "result"],
    },
    risk="low",
)
def memory_log_event(task: str = "", action: str = "", result: str = "",
                     agents: str = "", time: str = "") -> str:
    if not (task or action or result):
        return "至少填写 task / action / result 之一。"
    try:
        r = m3_store.log_episodic(task=task, action=action, result=result,
                                  agents=agents, event_time=time)
        return f"✓ 情景记忆已记录：{r['id']}（{r['time']}）"
    except Exception as exc:  # noqa: BLE001
        return f"情景记忆记录失败：{exc}"


@tool(
    name="memory_deep_dream",
    description=(
        "触发 Deep Dream 深度蒸馏：把情景记忆批量总结为语义记忆（LLM 可用时用 LLM，"
        "不可用时规则降级提取关键词与高频主题），支持手动触发与按间隔自动触发。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "force": {"type": "boolean", "description": "是否强制蒸馏（忽略间隔检查）"},
            "limit": {"type": "integer", "description": "最多蒸馏的情景事件数（默认 50）"},
            "interval_seconds": {"type": "integer", "description": "自动触发间隔秒数（默认 3600，force=true 时忽略）"},
        },
        "required": [],
    },
    risk="medium",
)
def memory_deep_dream(force: bool = False, limit: int = 50, interval_seconds: int = 3600) -> str:
    try:
        if force:
            return dream.deep_dream(limit=int(limit or 50), force=True)["message"]
        r = dream.maybe_auto_dream(interval_seconds=int(interval_seconds or 3600),
                                    limit=int(limit or 50))
        return r.get("message", str(r))
    except Exception as exc:  # noqa: BLE001
        return f"深度蒸馏失败：{exc}"


@tool(
    name="memory_query",
    description=(
        "按关键词检索三级记忆（语义>情景>工作 优先级 + 时间衰减），返回合并排序结果，"
        "供决策参考。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "查询关键词"},
            "limit": {"type": "integer", "description": "返回条数上限（默认 10）"},
        },
        "required": ["keyword"],
    },
    risk="low",
)
def memory_query(keyword: str = "", limit: int = 10) -> str:
    keyword = (keyword or "").strip()
    if not keyword:
        return "请输入查询关键词。"
    try:
        rows = m3_query.query(keyword=keyword, limit=limit)
        if not rows:
            return f"三级记忆中未找到与「{keyword}」相关的内容。"
        lines = [f"找到 {len(rows)} 条相关记忆（语义>情景>工作，按相关度排序）："]
        for r in rows:
            lines.append(f"- [{r['tier']}] {r['title']}（相关度 {r['score']}）：{r['snippet']}")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"记忆检索失败：{exc}"
