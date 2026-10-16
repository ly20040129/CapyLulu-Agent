"""UI 公共层：全局 Agent 单例、导航 / 示例常量、跨板块共享 helper。

从 app.py 拆出的公共依赖：所有视图模块（views_*）统一从这里取 agent 实例、
常量与基础函数，保证「单例一致 + 无循环 import」。
"""
from ..agent import Agent
from .. import agents_store
from .. import history as chatstore
from .. import tool_log
from ..config import config

# 全局 Agent，切模型 / 管家配置变更时 reconfigure()
agent = Agent()

PROVIDERS = ["zhipu", "deepseek"]
EXAMPLES = [
    "帮我看看当前目录有什么文件",
    "这台电脑配置怎么样",
    "打开记事本",
]
SKILLS = [
    "检查磁盘剩余空间",
    "打开 Windows 显示设置",
    "列出我桌面上的文件",
    "打开计算器",
    "现在几点了",
]
NAV = [
    "💬 对话", "👥 管家团队", "✨ 技能广场",
    "⏰ 自动任务", "🧠 用户记忆", "🛠 工具记录", "⚙️ 模型设置",
]


def _llm_ready() -> bool:
    """是否已填 API Key。"""
    return bool(config.llm_config.get("api_key"))


def _model_status_text() -> str:
    """侧栏底部状态。"""
    if _llm_ready():
        return f"🟢 已就绪 · {config.llm_provider} / {config.llm_config.get('model', '?')}"
    return "🟡 未配置 API Key"


def _specialist_choices() -> list[str]:
    """侧栏「当前管家」下拉选项：自动 + 启用的工作 Agent。"""
    return ["自动"] + agents_store.enabled_names()


def _choice_for(sess_id: str) -> str:
    """会话 id → 下拉展示名。"""
    return chatstore.title_of_id(sess_id) if sess_id else chatstore.session_choices()[0]


def _format_tools() -> str:
    """工具记录从持久化文件读取（追加式），页面加载不依赖内存态，杜绝“错误”。"""
    entries = tool_log.tail(240)
    if not entries:
        return "（噜噜在吃零食，还没有工具调用）"
    return "\n".join(entries)
