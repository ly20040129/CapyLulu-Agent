"""工具批量插件化：按 manifest 批量注册/注销工具，返回 Plugin 供插件注册表安装。

manifest: {"工具名": {"description":..., "parameters":..., "func":..., "risk":...}}
setup 注册全部；teardown 注销全部。
"""
from __future__ import annotations

from ..plugin import Plugin
from .registry import register_dynamic, unregister_dynamic


def plugin_tools(manifest: dict[str, dict], name: str = "plugin_tools",
                 version: str = "1.0", description: str = "") -> Plugin:
    """把一批工具打包成 Plugin（未安装，需调用 plugin.register() 生效）。

    manifest 中每个工具项支持字段：description / parameters / func / risk
    （risk 缺省 medium，与 register_dynamic 一致）。
    """

    def setup() -> None:
        for tool_name, spec in manifest.items():
            register_dynamic(
                name=tool_name,
                description=spec.get("description", ""),
                parameters=spec.get("parameters") or {},
                call_fn=spec.get("func"),
                risk=spec.get("risk", "medium"),
            )

    def teardown() -> None:
        for tool_name in manifest:
            unregister_dynamic(tool_name)

    return Plugin(
        name=name,
        version=version,
        description=description,
        setup=setup,
        teardown=teardown,
    )
