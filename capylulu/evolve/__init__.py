"""自主进化（批次7）：经验库 + 反思引擎 + 自我改进 + 自动触发。

对标 CowAgent 的 Agent 自主进化能力，构建「感知 → 沉淀 → 应用」闭环：

- lessons.py   经验库（data/evolve/lessons.json，增删查 + 应用计数 + 去重）
- reflect.py   反思引擎（从任务台账提炼经验，LLM / 规则降级，写经验库）
- improve.py   自我改进（基于经验生成改进建议，低风险自动应用，高风险记日志）
- maybe.py     maybe_evolve 触发（按间隔 / 新增任务数，时间戳判断）

数据目录迁移后调用 evolve.refresh_paths() 对齐路径。
"""
from . import improve, lessons, maybe, reflect

__all__ = ["lessons", "reflect", "improve", "maybe"]


def refresh_paths() -> None:
    """数据目录迁移后对齐 evolve 各模块路径常量。"""
    lessons.refresh_paths()
    improve.refresh_paths()
    maybe.refresh_paths()
