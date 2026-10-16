"""工作 Agent：文件 / 电脑 / 浏览器 / 软件 等，各自独立 system prompt 与工具集。

配置来源为 data/agents.json（agents_store）：支持动态增删改/启停，
被停用的 Agent 不参与 build_workers（Leader 路由也已跳过）。
"""
from .base import BaseAgent
from .. import agents_store


def build_workers(llm, max_iterations: int, max_history: int, tool_history: list[str]) -> dict[str, BaseAgent]:
    """按 agents_store 当前启用的 Agent 创建各工作 Agent（名称 → BaseAgent 实例）。"""
    workers = {}
    for a in agents_store.list_agents():
        name = a.get("name")
        if not name or name == "总代理":
            continue
        if not a.get("enabled", True):
            continue
        workers[name] = BaseAgent(
            name=name,
            system_prompt=a.get("prompt") or "",
            tools=a.get("tools") or None,
            llm=llm,
            max_iterations=max_iterations,
            max_history=max_history,
            tool_history=tool_history,
        )
    return workers


# 兼容旧引用：名称 → 独立 system prompt（动态读取当前配置）
WORKERS_SPEC = {
    a["name"]: a.get("prompt", "")
    for a in agents_store.list_agents()
    if a.get("name") != "总代理" and a.get("enabled", True)
}
