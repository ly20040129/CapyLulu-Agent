"""Agent 门面：保持原接口，内部为 Leader + 多个独立 Agent（File/Computer/Browser/App）。

- Leader（总代理）：闲聊直接答；识别意图后派发给对应工作 Agent；回传结果汇总。
- 工作 Agent（文件/电脑/浏览器/软件管家）：各自独立 system prompt、独立上下文、独立工具集。
"""
from ..config import config
from ..llm import create_llm
from .leader import LeaderAgent
from .router import classify, SPECIALISTS, _CHAT_ONLY, reload_routing
from .workers import build_workers


class Agent:
    """多 Agent 架构门面：Leader 调度 File/Computer/Browser/App 四个独立 Agent。"""

    def __init__(self):
        self.llm = create_llm()
        self.max_iterations = config.agent.get("max_iterations", 10)
        self.max_history = int(config.agent.get("max_history", 32))
        self.tool_history: list[str] = []
        self.last_specialist = "总代理"
        self.leader = LeaderAgent(self.llm, self.max_iterations, self.max_history, self.tool_history)
        self.workers = build_workers(self.llm, self.max_iterations, self.max_history, self.tool_history)

    def reconfigure(self):
        """模型设置 / 管家团队配置变更后：重建 LLM、路由表与工作 Agent。"""
        self.llm = create_llm()
        self.max_iterations = config.agent.get("max_iterations", 10)
        self.max_history = int(config.agent.get("max_history", 32))
        reload_routing()
        self.leader.llm = self.llm
        self.leader.max_iterations = self.max_iterations
        self.leader.max_history = self.max_history
        # 重建工作 Agent（增删改/启停后生效；新实例保留原 tool_history 引用）
        self.workers = build_workers(self.llm, self.max_iterations, self.max_history, self.tool_history)
        for w in self.workers.values():
            w.llm = self.llm
            w.max_iterations = self.max_iterations
            w.max_history = self.max_history

    def run(self, user_input: str, chat_history: list | None = None, specialist: str = "自动") -> str:
        """Leader 接收用户输入：路由 → 派发 → 汇总。

        - 闲聊/问答 → Leader 直接答（不带工具）。
        - 未命中任何专员（兜底）→ Leader 使用全量工具自己处理（保持原有兜底能力）。
        - 命中专员 → 工作 Agent 用独立上下文执行，结果回传 Leader 汇总。
        """
        pinned = None if specialist in (None, "自动") else specialist
        who = classify(user_input, pinned)
        self.last_specialist = who
        self.tool_history.clear()
        self.tool_history.append(f"👤 总代理 → {who}")

        # 首次运行时把外部全局历史注入各 Agent 的独立上下文
        self.leader.seed_history(chat_history)
        for w in self.workers.values():
            w.seed_history(chat_history)

        if who == "总代理":
            if _CHAT_ONLY.match(user_input.strip()):
                return self.leader.chat_only(user_input)
            # 带队型调度：Leader 决策 chat / direct / plan，复杂任务拆解给多个管家协作
            return self.leader.run_orchestrated(user_input, self.workers)

        worker = self.workers.get(who)
        if worker is None:
            # 目标 Agent 已被停用/删除：Leader 兜底处理
            return self.leader.run_task(user_input, use_all_tools=True)
        result = worker.run_task(user_input)
        return self.leader.summarize(who, result)
