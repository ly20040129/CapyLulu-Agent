"""工具注册表 + 安全分级 + P0 工具流水线钩子"""
import functools
import json
import time
from typing import Callable

from ..config import config

# 风险等级
LOW = "low"       # 自动执行
MEDIUM = "medium"  # 记录日志（P1 先不弹确认）
HIGH = "high"     # 禁止自动执行（默认 deny，见审批策略）

_tool_registry: dict[str, dict] = {}

# 一次性质押集合：{(name, canonical_arguments_json)}，approve_tool 放行后
# call_tool 中 HIGH 工具在 policy==ask 时可执行一次，执行后自动清除。
_approved_once: set[tuple[str, str]] = set()

# 审批策略配置键：auto（放行 HIGH）/ ask（返回审批提示）/ deny（禁止自动执行，默认）
APPROVAL_POLICY = "approval_policy"


class ToolBlocked(Exception):
    """pre 钩子抛出的阻断异常：call_tool 捕获后返回阻断原因，不执行工具。"""


# P0 工具流水线钩子：kind ∈ {"pre", "post"}
_pre_hooks: list[Callable] = []
_post_hooks: list[Callable] = []


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
    """执行工具（含安全检查 + 审批策略 + pre/post 钩子流水线 + 计时）"""
    entry = _tool_registry.get(name)
    if not entry:
        return f"未知工具: {name}"
    # 防御：LLM 可能传 None / 非 dict（如 null、[]），避免 **None 崩溃
    if not isinstance(arguments, dict):
        arguments = {}
    if entry["risk"] == HIGH:
        # 审批策略：默认 deny 与现有行为一致（高风险禁止自动执行）
        policy = config.agent.get(APPROVAL_POLICY, "deny")
        if policy == "ask":
            # 存在一次性质押（approve_tool 放行）时允许执行一次，执行后自动清除
            key = (name, json.dumps(arguments, sort_keys=True, ensure_ascii=False))
            if key in _approved_once:
                _approved_once.discard(key)
            else:
                return f"需要审批：工具 {name}（参数 {arguments}）。输入「批准 {name}」继续"
        elif policy != "auto":
            # deny（默认）：即使有质押也仍禁止，保持默认安全边界
            return f"工具 {name} 为高风险操作，禁止自动执行"
    # 参数完整性校验：LLM 偶发返回空 arguments（空串/null）时，直接展开调用会抛
    # "missing N required positional arguments" 的 TypeError，既不友好也无法引导重试。
    # 改为按 schema 的 required 校验，缺失时返回明确提示，LLM 可据此补参后重试。
    params_schema = entry.get("schema", {}).get("function", {}).get("parameters") or {}
    required = params_schema.get("required") or []
    missing = [k for k in required if k not in arguments]
    if missing:
        return (f"工具 {name} 参数缺失（失败）：缺少必需参数 {', '.join(missing)}；"
                "请先获取必要信息（如路径、内容）后补齐参数再重新调用。")
    # pre 钩子链：返回 dict 改写参数；返回 None 放行；抛 ToolBlocked 阻断
    for fn in list(_pre_hooks):
        try:
            ret = fn(name, arguments)
        except ToolBlocked as e:
            return f"工具 {name} 被阻断：{e}"
        if isinstance(ret, dict):
            arguments = ret
    t0 = time.time()
    try:
        result = entry["func"](**arguments)
    except ToolBlocked as e:
        return f"工具 {name} 被阻断：{e}"
    elapsed_ms = int((time.time() - t0) * 1000)
    # post 钩子链：返回 str 改写结果；异常包装，保证始终返回字符串
    try:
        for fn in list(_post_hooks):
            ret = fn(name, arguments, result, elapsed_ms)
            if ret is not None and isinstance(ret, str):
                result = ret
    except ToolBlocked as e:
        return f"工具 {name} 被阻断：{e}"
    except Exception as e:  # noqa: BLE001
        return f"工具执行出错: {e}"
    return result


def get_risk_level(name: str) -> str:
    """获取工具的风险等级"""
    entry = _tool_registry.get(name, {})
    return entry.get("risk", "unknown")


# ---------------- 审批：一次性质押 ----------------

def approve_once(name: str, arguments: dict | None = None) -> bool:
    """给指定工具放行一次（HIGH 工具在 policy==ask 时可执行一次）。

    arguments 与目标调用参数一致时精确匹配；缺省空 dict（放行空参数调用）。
    返回是否真的建立质押（工具不存在时返回 False）。
    """
    if not name or name not in _tool_registry:
        return False
    args = arguments if isinstance(arguments, dict) else {}
    key = (name, json.dumps(args, sort_keys=True, ensure_ascii=False))
    _approved_once.add(key)
    return True


def reject_approval(name: str) -> bool:
    """撤销指定工具的全部一次性质押；返回是否真的撤销了质押。"""
    if not name:
        return False
    removed = False
    for key in list(_approved_once):
        if key[0] == name:
            _approved_once.discard(key)
            removed = True
    return removed


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


# ---------------- P0 工具流水线钩子 ----------------

def add_hook(kind: str, fn: Callable) -> bool:
    """注册工具流水线钩子；kind ∈ {"pre", "post"}；同名不重复注册。

    pre:  fn(name, arguments) -> dict | None
        返回 dict 则替换 arguments（可补参/改参）；返回 None 则放行；
        抛 ToolBlocked(原因) 则阻断执行，call_tool 返回原因。
    post: fn(name, arguments, result, elapsed_ms) -> str | None
        返回 str 则替换结果。
    """
    if kind == "pre":
        if fn not in _pre_hooks:
            _pre_hooks.append(fn)
            return True
    elif kind == "post":
        if fn not in _post_hooks:
            _post_hooks.append(fn)
            return True
    return False


def remove_hook(kind: str, fn: Callable) -> bool:
    """移除工具流水线钩子；返回是否真的移除。"""
    if kind == "pre":
        try:
            _pre_hooks.remove(fn)
            return True
        except ValueError:
            return False
    if kind == "post":
        try:
            _post_hooks.remove(fn)
            return True
        except ValueError:
            return False
    return False


def clear_hooks(kind: str | None = None) -> int:
    """清空钩子；kind 为 None 时清空全部。返回清理数量。"""
    n = 0
    if kind in (None, "pre"):
        n += len(_pre_hooks)
        _pre_hooks.clear()
    if kind in (None, "post"):
        n += len(_post_hooks)
        _post_hooks.clear()
    return n
