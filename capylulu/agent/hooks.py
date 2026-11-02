"""Agent 循环钩子：before_llm / after_llm / before_tool / after_tool 四阶段。

- AgentHooks：实例级监听器容器，BaseAgent 通过 hooks 参数注入；
- 模块级注册表：register_loop_hook / remove_loop_hook 注入全局钩子，
  插件可无侵入地为所有 Agent 挂阶段钩子。
"""
from __future__ import annotations

from typing import Callable

PHASES = ("before_llm", "after_llm", "before_tool", "after_tool")

# 模块级全局钩子注册表：phase -> [fn]
_loop_hooks: dict[str, list[Callable]] = {p: [] for p in PHASES}


def register_loop_hook(phase: str, fn: Callable) -> bool:
    """注册全局循环钩子（phase ∈ PHASES）；同名不重复注册。"""
    if phase not in PHASES or fn is None:
        return False
    if fn not in _loop_hooks[phase]:
        _loop_hooks[phase].append(fn)
        return True
    return False


def remove_loop_hook(phase: str, fn: Callable) -> bool:
    """移除全局循环钩子；返回是否真的移除。"""
    if phase not in PHASES:
        return False
    try:
        _loop_hooks[phase].remove(fn)
        return True
    except ValueError:
        return False


class AgentHooks:
    """实例级阶段钩子容器。

    钩子语义：
    - before_llm(messages, tools) -> (messages, tools) | None   可改写，None 放行
    - after_llm(resp) -> dict | None                            可改写 resp
    - before_tool(name, arguments) -> dict | None               可改写参数
    - after_tool(name, arguments, result) -> str | None         可改写结果
    同一阶段按注册顺序执行；全局钩子（register_loop_hook）在实例监听器之后执行。
    """

    def __init__(self, listeners: dict[str, list[Callable]] | None = None):
        self._listeners: dict[str, list[Callable]] = {p: [] for p in PHASES}
        if listeners:
            for phase, fns in listeners.items():
                for fn in fns:
                    self.add_listener(phase, fn)

    def add_listener(self, phase: str, fn: Callable) -> bool:
        if phase not in PHASES or fn is None:
            return False
        if fn not in self._listeners[phase]:
            self._listeners[phase].append(fn)
            return True
        return False

    def remove_listener(self, phase: str, fn: Callable) -> bool:
        if phase not in PHASES:
            return False
        try:
            self._listeners[phase].remove(fn)
            return True
        except ValueError:
            return False

    # ---------------- 阶段执行 ----------------

    def before_llm(self, messages: list, tools):
        out_m, out_t = messages, tools
        for fn in list(self._listeners["before_llm"]) + list(_loop_hooks["before_llm"]):
            ret = fn(out_m, out_t)
            if ret is not None:
                out_m, out_t = ret
        return out_m, out_t

    def after_llm(self, resp: dict) -> dict:
        out = resp
        for fn in list(self._listeners["after_llm"]) + list(_loop_hooks["after_llm"]):
            ret = fn(out)
            if ret is not None:
                out = ret
        return out

    def before_tool(self, name: str, arguments: dict) -> dict:
        out = arguments
        for fn in list(self._listeners["before_tool"]) + list(_loop_hooks["before_tool"]):
            ret = fn(name, out)
            if ret is not None:
                out = ret
        return out

    def after_tool(self, name: str, arguments: dict, result: str) -> str:
        out = result
        for fn in list(self._listeners["after_tool"]) + list(_loop_hooks["after_tool"]):
            ret = fn(name, arguments, out)
            if ret is not None:
                out = ret
        return out
