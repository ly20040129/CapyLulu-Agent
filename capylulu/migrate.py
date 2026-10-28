"""数据目录迁移：把现有数据文件（sessions/tasks/logs/agents/skills/memory）复制到
新 data_dir 并写回 config.yaml，随后刷新各存储模块路径。

安全策略：只复制不删除源文件（可逆），目标已存在的同名文件自动跳过避免覆盖。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from loguru import logger

from .config import PROJECT_ROOT, config

# 需随 data_dir 迁移的数据（文件或目录）
MIGRATE_NAMES = [
    "sessions.json",      # 对话历史
    "tasks.json",         # 自动任务
    "task_logs.json",     # 任务执行记录
    "tool_logs.json",     # 工具调用记录
    "agents.json",        # 管家团队
    "skills.json",        # 技能广场
    "notes",              # 便签目录
    "memory",             # 用户记忆目录
]


def _resolve(new_dir: str) -> Path | None:
    new_dir = (new_dir or "").strip()
    if not new_dir:
        return None
    p = Path(new_dir)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.resolve()


def migrate_data_dir(new_dir: str) -> tuple[str, bool]:
    """迁移数据到新目录，返回 (消息, 是否成功)。"""
    target = _resolve(new_dir)
    if target is None:
        logger.error("[Migrate] 数据目录不能为空")
        return "数据目录不能为空", False
    old = config.data_dir
    if target == old:
        logger.info(f"[Migrate] 新目录与当前一致（{old}），无需迁移")
        return f"新目录与当前一致（{old}），无需迁移", False
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[Migrate] 创建目标目录失败：{exc}")
        return f"创建目标目录失败：{exc}", False

    moved: list[str] = []
    skipped: list[str] = []
    for name in MIGRATE_NAMES:
        src = old / name
        if not src.exists():
            skipped.append(f"{name}（源不存在）")
            continue
        dst = target / name
        if dst.exists():
            skipped.append(f"{name}（目标已存在，跳过避免覆盖）")
            continue
        try:
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            moved.append(name)
        except Exception as exc:  # noqa: BLE001
            skipped.append(f"{name}（复制失败：{exc}）")
            logger.error(f"[Migrate] 迁移 {name} 失败：{exc}")

    cfg_msg = config.update_data_dir(str(target))
    # 刷新各存储模块路径常量
    from . import history, tasks, tool_log, agents_store, skills_store, memory  # noqa: PLC0415

    for mod in (history, tasks, tool_log, agents_store, skills_store, memory):
        mod.refresh_paths()

    if cfg_msg != str(target):
        logger.error(f"[Migrate] 数据已迁移但配置写回失败：{cfg_msg}")
        return f"⚠️ 数据已迁移到 {target}，但配置写回失败：{cfg_msg}", False
    logger.info(f"[Migrate] 数据目录已迁移到：{target}")
    detail = (
        f"已迁移：{', '.join(moved) if moved else '无'}\n"
        f"跳过：{', '.join(skipped) if skipped else '无'}"
    )
    return f"✓ 数据目录已更新为 {target}\n{detail}", True
