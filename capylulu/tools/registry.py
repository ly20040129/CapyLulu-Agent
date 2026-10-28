"""工具注册表 + 安全分级"""
import functools
from typing import Callable

# 风险等级
LOW = "low"       # 自动执行
MEDIUM = "medium"  # 记录日志（P1 先不弹确认）
HIGH = "high"     # 禁止自动执行

_tool_registry: dict[str, dict] = {}


def tool(name: str, description: str, parameters: dict, risk: str = LOW):
    """工具注册装饰器：把普通函数注册为 LLM 可调用的工具"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(**kwargs) -> str:
            try:
                result = func(**kwargs)
                return str(result) if not isinstance(result, str) else result
            except Exception as e:
                return f"工具执行出错: {e}"

        _tool_registry[name] = {
            "func": wrapper,
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            "risk": risk,
        }
        return wrapper

    return decorator


def get_tool_schemas(names: list[str] | None = None) -> list[dict]:
    """获取工具 schema；names 为空则返回全部。"""
    if names is None:
        return [t["schema"] for t in _tool_registry.values()]
    return [t["schema"] for n, t in _tool_registry.items() if n in names]


def call_tool(name: str, arguments: dict) -> str:
    """执行工具（含安全检查）"""
    entry = _tool_registry.get(name)
    if not entry:
        return f"未知工具: {name}"
    if entry["risk"] == HIGH:
        return f"工具 {name} 为高风险操作，禁止自动执行"
    # 防御：LLM 可能传 None / 非 dict（如 null、[]），避免 **None 崩溃
    if not isinstance(arguments, dict):
        arguments = {}
    # 参数完整性校验：LLM 偶发返回空 arguments（空串/null）时，直接展开调用会抛
    # "missing N required positional arguments" 的 TypeError，既不友好也无法引导重试。
    # 改为按 schema 的 required 校验，缺失时返回明确提示，LLM 可据此补参后重试。
    params_schema = entry.get("schema", {}).get("function", {}).get("parameters") or {}
    required = params_schema.get("required") or []
    missing = [k for k in required if k not in arguments]
    if missing:
        return (f"工具 {name} 参数缺失（失败）：缺少必需参数 {', '.join(missing)}；"
                "请先获取必要信息（如路径、内容）后补齐参数再重新调用。")
    return entry["func"](**arguments)


def get_risk_level(name: str) -> str:
    """获取工具的风险等级"""
    entry = _tool_registry.get(name, {})
    return entry.get("risk", "unknown")


# ---------------- 动态注册（MCP 热接入等） ----------------

def register_dynamic(name: str, description: str, parameters: dict, call_fn, risk: str = MEDIUM) -> None:
    """动态注册工具（如 MCP 工具热接入），与 @tool 等效进入主注册表。

    call_fn 为可调用对象，签名 **kwargs -> str；调用时由 registry 统一包装并捕获异常。
    """
    def wrapper(**kwargs):
        try:
            result = call_fn(**kwargs)
            return str(result) if not isinstance(result, str) else result
        except Exception as e:  # noqa: BLE001
            return f"工具执行出错: {e}"

    _tool_registry[name] = {
        "func": wrapper,
        "schema": {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters or {"type": "object", "properties": {}},
            },
        },
        "risk": risk,
    }


def unregister_dynamic(name: str) -> bool:
    """注销指定动态工具；返回是否真的移除。"""
    return _tool_registry.pop(name, None) is not None


def clear_dynamic(prefix: str = "mcp_") -> int:
    """批量注销以 prefix 开头的动态工具（重刷前先清旧）；返回清理数量。"""
    keys = [k for k in _tool_registry if k.startswith(prefix)]
    for k in keys:
        _tool_registry.pop(k, None)
    return len(keys)


def registered_names() -> list[str]:
    """当前注册表中全部工具名（静态 + 动态）。"""
    return list(_tool_registry.keys())
