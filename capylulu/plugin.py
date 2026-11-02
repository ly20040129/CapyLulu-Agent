"""插件注册表：Plugin dataclass + register/unregister + 副作用自动撤销。

每个插件只声明 setup / teardown 两个副作用钩子：
- register() 调用 setup（注册副作用，如注册工具 / 添加 provider / 挂钩子）；
- unregister() 调用 teardown 自动撤销副作用；
- setup 抛异常时自动回滚（调用 teardown）并返回 False，同名插件拒绝注册。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Plugin:
    name: str
    version: str = "1.0"
    description: str = ""
    # setup/teardown 为可调用对象，分别注册/撤销注册副作用
    setup: Callable[[], None] | None = None
    teardown: Callable[[], None] | None = None
    deps: list[str] = field(default_factory=list)  # 依赖的其他插件名


_plugins: dict[str, Plugin] = {}


def register(plugin: Plugin) -> bool:
    """注册插件：调用 setup；同名拒绝；setup 异常自动回滚并返回 False。"""
    if not isinstance(plugin, Plugin) or not plugin.name:
        return False
    if plugin.name in _plugins:
        return False
    _plugins[plugin.name] = plugin
    if plugin.setup is not None:
        try:
            plugin.setup()
        except Exception:
            _plugins.pop(plugin.name, None)
            if plugin.teardown is not None:
                try:
                    plugin.teardown()
                except Exception:
                    pass
            return False
    return True


def unregister(name: str) -> bool:
    """卸载插件：调用 teardown 撤销副作用；无 teardown 时仅移除。"""
    plugin = _plugins.pop(name, None)
    if plugin is None:
        return False
    if plugin.teardown is not None:
        try:
            plugin.teardown()
        except Exception:
            pass
    return True


def is_registered(name: str) -> bool:
    return name in _plugins


def registered_plugins() -> list[Plugin]:
    return list(_plugins.values())
