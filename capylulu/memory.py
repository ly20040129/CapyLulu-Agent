"""用户记忆存储：<data_dir>/memory/ 下的 md 文件（每篇一篇记忆，可自定义修改 / 移动位置）。

支持：创建 / 读取 / 编辑保存（UTF-8 中文）/ 删除（优先回收站）。
记忆条目首行带 owner 标记（<!-- owner: xxx -->），未登录为 default；旧文件无标记按 default 兼容。
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from loguru import logger

from . import auth
from .config import config

MEMORY_DIR = config.data_dir / "memory"  # 用户记忆目录
OWNER_MARK = "<!-- owner:"  # 记忆 owner 标记（文件首行）


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global MEMORY_DIR
    MEMORY_DIR = config.data_dir / "memory"


def _safe_name(name: str) -> str:
    """清洗文件名：去路径分隔与非法字符，防路径遍历。"""
    name = (name or "").strip()
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name)
    return name[:60]


def _current_owner() -> str:
    """当前身份 uid，未登录为 default。"""
    user = auth.current_user()
    return str(user.get("uid")) if user and user.get("uid") else "default"


def _owner_mark(owner: str) -> str:
    """生成记忆 owner 标记行。"""
    return f"<!-- owner: {owner} -->\n"


def _read_owner(p: Path) -> str:
    """读取记忆文件首行 owner 标记；无标记默认 default。"""
    try:
        first = p.read_text(encoding="utf-8").splitlines()[0] if p.exists() else ""
    except Exception:  # noqa: BLE001
        first = ""
    if first.startswith(OWNER_MARK):
        return first.replace(OWNER_MARK, "").replace("-->", "").strip() or "default"
    return "default"


def _split_owner(content: str) -> tuple[str, str]:
    """解析内容首行的 owner 标记，返回 (owner, 正文)；无标记正文原样返回。"""
    lines = (content or "").splitlines()
    if lines and lines[0].startswith(OWNER_MARK):
        owner = lines[0].replace(OWNER_MARK, "").replace("-->", "").strip() or "default"
        return owner, "\n".join(lines[1:]).lstrip("\n")
    return "default", content


def list_memories() -> list[dict]:
    """返回 [{name, size, mtime, owner}]，按修改时间倒序。"""
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
            "owner": _read_owner(p),
        })
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows


def memory_choices() -> list[str]:
    """记忆文件名列表（下拉选择用）。"""
    return [r["name"] for r in list_memories()]


def read_memory(name: str) -> str:
    """读取记忆内容（剥离 owner 标记行；仅限 memory 目录内的 .md 文件）。"""
    p = MEMORY_DIR / _safe_name(name)
    if not p.exists() or not p.is_file() or p.suffix.lower() != ".md":
        return ""
    return _split_owner(p.read_text(encoding="utf-8"))[1]


def create_memory(name: str, content: str = "") -> str:
    """新建记忆文件（自动带 owner 标记）；返回状态消息。"""
    name = _safe_name(name)
    if not name:
        return "记忆标题不能为空"
    if not name.endswith(".md"):
        name += ".md"
    p = MEMORY_DIR / name
    if p.exists():
        return f"已存在同名记忆：{name}"
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    owner = _current_owner()
    p.write_text(_owner_mark(owner) + (content or f"# {name[:-3]}\n\n"), encoding="utf-8")
    logger.info(f"[Memory] 已新建记忆：{name}（{owner}）")
    return f"✓ 已新建记忆「{name}」"


def save_memory(name: str, content: str) -> str:
    """编辑保存记忆内容（自动刷新 owner 标记）；返回状态消息。"""
    name = _safe_name(name)
    if not name:
        return "记忆标题不能为空"
    if not name.endswith(".md"):
        name += ".md"
    p = MEMORY_DIR / name
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    owner = _current_owner()
    body = _split_owner(content or "")[1]
    p.write_text(_owner_mark(owner) + body, encoding="utf-8")
    logger.info(f"[Memory] 已保存记忆：{name}（{owner}）")
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
            logger.info(f"[Memory] 已删除（回收站）：{p.name}")
            return f"✓ 已删除（移入回收站）「{p.name}」"
        except Exception:  # 未安装时降级永久删除
            p.unlink()
            logger.info(f"[Memory] 已永久删除（未装 send2trash）：{p.name}")
            return f"✓ 已永久删除「{p.name}」（本机未装 send2trash）"
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[Memory] 删除失败：{exc}")
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
