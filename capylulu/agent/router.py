"""意图识别路由：Leader 派发工作 Agent 的依据（规则 + 工具名匹配）。

数据来源改为 data/agents.json（agents_store），支持管家团队页动态增删改/启停：
- reload_routing() 在 Agent 配置变更后刷新 SPECIALISTS / _RULES / TOOL_OWNER；
- 被停用的 Agent 不参与 SPECIALISTS/_RULES/TOOL_OWNER，classify 会跳过它。
"""
import re

from .. import agents_store

_CHAT_ONLY = re.compile(
    r"^(你好|您好|嗨|哈喽|hello|hi|hey|在吗|在嘛|早上好|晚上好|午安|"
    r"你是谁|你叫什么|介绍一下你自己|噜噜|卡皮|水豚|谢谢|再见|拜拜).{0,12}$",
    re.I,
)


def _build():
    """从 agents_store 构建当前路由表（仅启用 Agent）。"""
    specialists = {"总代理": None}  # None = 不强制工具集，闲聊不带工具
    rules = []
    tool_owner = {}
    for a in agents_store.list_agents():
        name = a.get("name")
        if not name or name == "总代理":
            continue
        if not a.get("enabled", True):
            continue
        tools = a.get("tools") or []
        specialists[name] = tools or None
        for kw in a.get("keywords") or []:
            if kw:
                rules.append((name, (kw,)))
        for t in tools:
            tool_owner[t] = name
    return specialists, rules, tool_owner


# 各管家可用工具（工具名匹配用）
SPECIALISTS = {"总代理": None}
# 工具名 → 所属管家（用户直接提到工具名时精准路由）
TOOL_OWNER: dict[str, str] = {}
# 关键词 → 管家（按优先级从高到低，命中即返回）
_RULES: list[tuple[str, tuple[str, ...]]] = []


def reload_routing() -> None:
    """Agent 配置变更后刷新全局路由表。"""
    global SPECIALISTS, _RULES, TOOL_OWNER
    SPECIALISTS, _RULES, TOOL_OWNER = _build()


reload_routing()  # 模块加载时初始化一次


def classify(text: str, pinned: str | None = None) -> str:
    """意图识别：pinned 指定优先 → 闲聊 → 工具名精准匹配 → 关键词规则 → 兜底总代理。"""
    if pinned and pinned in SPECIALISTS and pinned != "自动":
        return pinned
    t = (text or "").strip()
    if not t:
        return "总代理"
    low = t.lower()
    if _CHAT_ONLY.match(t):
        return "总代理"
    # 工具名直接命中 → 所属管家（如用户说「用 list_desktop 看看」）
    for token in re.findall(r"[a-z_]+", low):
        if token in TOOL_OWNER:
            return TOOL_OWNER[token]
    # 关键词规则（顺序即优先级）
    hits = []
    for who, keys in _RULES:
        if any(k in low for k in keys):
            hits.append(who)
    uniq: list[str] = []
    for w in hits:
        if w not in uniq:
            uniq.append(w)
    if len(uniq) >= 2:
        # 同时命中多个专员领域（如“浏览器提取+文件保存”）→ 跨域复杂任务，
        # 交由总代理带队拆解，由规划引擎分步派发给各专员协作闭环。
        return "总代理"
    if uniq:
        return uniq[0]
    return "总代理"
