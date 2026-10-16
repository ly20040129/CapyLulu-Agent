"""用户记忆存储：<data_dir>/memory/ 下的 md 文件（每篇一篇记忆，可自定义修改 / 移动位置）。

支持：创建 / 读取 / 编辑保存（UTF-8 中文）/ 删除（优先回收站）。
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from .config import config

MEMORY_DIR = config.data_dir / "memory"


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global MEMORY_DIR
    MEMORY_DIR = config.data_dir / "memory"


def _safe_name(name: str) -> str:
    """清洗文件名：去路径分隔与非法字符，防路径遍历。"""
    name = (name or "").strip()
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name)
    return name[:60]


def list_memories() -> list[dict]:
    """返回 [{name, size, mtime}]，按修改时间倒序。"""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in MEMORY_DIR.glob("*.md"):
        if not p.is_file():
            continue
        st = p.stat()
        rows.append({
            "name": p.name,
            "size": st.st_size,
            "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
        })
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows


def memory_choices() -> list[str]:
    """记忆文件名列表（下拉选择用）。"""
    return [r["name"] for r in list_memories()]


def read_memory(name: str) -> str:
    """读取记忆内容（仅限 memory 目录内的 .md 文件）。"""
    p = MEMORY_DIR / _safe_name(name)
    if not p.exists() or not p.is_file() or p.suffix.lower() != ".md":
        return ""
    return p.read_text(encoding="utf-8")


def create_memory(name: str, content: str = "") -> str:
    """新建记忆文件；返回状态消息。"""
    name = _safe_name(name)
    if not name:
        return "记忆标题不能为空"
    if not name.endswith(".md"):
        name += ".md"
    p = MEMORY_DIR / name
    if p.exists():
        return f"已存在同名记忆：{name}"
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(content or f"# {name[:-3]}\n\n", encoding="utf-8")
    return f"✓ 已新建记忆「{name}」"


def save_memory(name: str, content: str) -> str:
    """编辑保存记忆内容；返回状态消息。"""
    name = _safe_name(name)
    if not name:
        return "记忆标题不能为空"
    if not name.endswith(".md"):
        name += ".md"
    p = MEMORY_DIR / name
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(content or "", encoding="utf-8")
    return f"✓ 已保存「{name}」"


def delete_memory(name: str) -> str:
    """删除记忆（优先移入回收站）；返回状态消息。"""
    p = MEMORY_DIR / _safe_name(name)
    if not p.exists() or not p.is_file():
        return f"记忆不存在：{name}"
    try:
        try:
            import send2trash  # 优先回收站

            send2trash.send2trash(str(p))
            return f"✓ 已删除（移入回收站）「{p.name}」"
        except Exception:  # 未安装时降级永久删除
            p.unlink()
            return f"✓ 已永久删除「{p.name}」（本机未装 send2trash）"
    except Exception as exc:  # noqa: BLE001
        return f"删除失败：{exc}"


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1048576:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1048576:.1f} MB"


def rows() -> list[list]:
    """记忆页 Dataframe：标题 / 大小 / 更新时间。"""
    return [[r["name"], _fmt_size(r["size"]), r["mtime"]] for r in list_memories()]
