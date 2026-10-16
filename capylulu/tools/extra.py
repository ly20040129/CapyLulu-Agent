"""演示型小工具集（tools/extra.py）。

面向「未配置 API Key 也能演示 Agent 能力」的本地小工具：
剪贴板读写、生成便签、打开常用应用、读写用户记忆。

设计约束：
- 工具名不与 desktop.py / file_ops.py 重名；
- 全部只读或仅写入项目数据目录（<data_dir>/notes、<data_dir>/memory）；
- schema 规范（LLM 可解析的 JSON Schema），异常容错（失败返回中文原因而非抛错）。
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .. import memory as memory_store
from ..config import config
from .registry import tool


# ---------------- 剪贴板 ----------------

def _clipboard_via_tk(action: str, text: str = "") -> str:
    """用 tkinter 读写系统剪贴板（无第三方依赖）。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        if action == "read":
            return root.clipboard_get() or ""
        root.clipboard_clear()
        root.clipboard_append(text or "")
        root.update()
        return ""
    except Exception as exc:  # noqa: BLE001
        return f"剪贴板访问失败：{exc}"
    finally:
        try:
            root.destroy()
        except Exception:  # noqa: BLE001
            pass


@tool(
    name="clipboard_read",
    description="读取系统剪贴板当前文本内容（只读，不修改任何东西）。",
    parameters={"type": "object", "properties": {}, "required": []},
    risk="low",
)
def clipboard_read() -> str:
    content = _clipboard_via_tk("read")
    if not content:
        return "剪贴板为空（或没有文本内容）。"
    return f"剪贴板内容：\n{content}"


@tool(
    name="clipboard_write",
    description="把指定文本写入系统剪贴板（复制到剪贴板，方便用户粘贴）。",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string", "description": "要复制到剪贴板的文本内容"}},
        "required": ["text"],
    },
    risk="low",
)
def clipboard_write(text: str = "") -> str:
    text = (text or "").strip()
    if not text:
        return "没有可写入剪贴板的文本。"
    err = _clipboard_via_tk("write", text)
    if err:
        return err
    return f"✓ 已复制到剪贴板（{len(text)} 字符）。"


# ---------------- 便签 ----------------

@tool(
    name="make_note",
    description="生成一张本地便签：写入 <data_dir>/notes/ 下的 md 文件，内容包含触发时间和便签正文。用于提醒、备忘、记事。",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string", "description": "便签正文内容"}},
        "required": ["text"],
    },
    risk="medium",
)
def make_note(text: str = "") -> str:
    text = (text or "").strip()
    if not text:
        return "便签内容不能为空。"
    from ..scheduler import write_note  # 复用调度器的便签生成（防重名）

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        p = write_note(text, ts)
    except Exception as exc:  # noqa: BLE001
        return f"便签生成失败：{exc}"
    return f"✓ 便签已生成：{p}"


# ---------------- 打开常用应用 ----------------

# 内置 Windows 应用映射（可安全演示的常见应用）
_APP_ALIASES = {
    "记事本": "notepad",
    "notepad": "notepad",
    "计算器": "calc",
    "calc": "calc",
    "画图": "mspaint",
    "paint": "mspaint",
    "mspaint": "mspaint",
    "截图工具": "snippingtool",
    "截图": "snippingtool",
    "录音机": "ms-call",
    "录音": "ms-call",
    "照片": "ms-photos",
    "照片查看器": "ms-photos",
    "资源管理器": "explorer",
    "explorer": "explorer",
    "终端": "wt",
    "终端窗口": "wt",
    "相机": "ms-camera",
    "相机应用": "ms-camera",
    "设置": "ms-settings",
}

_KNOWN_APPS = "、".join(sorted({k for k in _APP_ALIASES if not k.isascii()}))
# 避免枚举与个别英文别名重复展示


@tool(
    name="launch_common_app",
    description=(
        "打开本机常用 Windows 应用（记事本/计算器/画图/截图工具/录音机/照片/资源管理器/终端/设置等），"
        f"支持：{_KNOWN_APPS}。仅启动应用，不修改系统设置。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "应用名称，如 记事本、计算器、画图、截图工具、录音机、照片、资源管理器、终端",
                "enum": sorted({k for k in _APP_ALIASES if not k.isascii()}),
            }
        },
        "required": ["name"],
    },
    risk="medium",
)
def launch_common_app(name: str = "") -> str:
    key = (name or "").strip().lower()
    target = _APP_ALIASES.get(name, "") or _APP_ALIASES.get(key, "")
    if not target:
        return f"暂不支持打开「{name}」，支持：{_KNOWN_APPS}。"
    try:
        if target.startswith("ms-"):
            # UWP 协议：ms-call: / ms-photos: / ms-settings:
            subprocess.Popen(["cmd", "/c", "start", "", f"{target}:"], shell=False)
        else:
            os.startfile(target)  # noqa: S606 仅启动白名单内置应用
        return f"✓ 已打开 {name}（{target}）。"
    except Exception as exc:  # noqa: BLE001
        return f"打开 {name} 失败：{exc}"


# ---------------- 用户记忆 ----------------

@tool(
    name="memory_read",
    description="读取一条用户记忆（<data_dir>/memory/ 下的 md 文件）。不指定标题时返回记忆列表。",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "记忆文件名（可省略，省略时返回全部记忆标题列表）"}
        },
        "required": [],
    },
    risk="low",
)
def memory_read(name: str = "") -> str:
    name = (name or "").strip()
    rows = memory_store.list_memories()
    if not rows:
        return "还没有用户记忆。可以让我「记住 xxx」创建一条。"
    if not name:
        lines = "\n".join(f"- {r['name']}（{r['mtime']}）" for r in rows)
        return f"当前共有 {len(rows)} 条记忆：\n{lines}"
    content = memory_store.read_memory(name)
    if not content:
        return f"没有找到记忆「{name}」。现有记忆：{', '.join(r['name'] for r in rows)}"
    return content.strip() or f"「{name}」内容为空。"


@tool(
    name="memory_write",
    description="写入一条用户记忆（<data_dir>/memory/ 下的 md 文件）。同名记忆会被覆盖更新；标题自动补 .md 后缀。",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "记忆标题（如：我的生日、老板电话）"},
            "content": {"type": "string", "description": "要记住的内容正文"},
        },
        "required": ["name", "content"],
    },
    risk="medium",
)
def memory_write(name: str = "", content: str = "") -> str:
    name = (name or "").strip()
    content = (content or "").strip()
    if not name:
        return "记忆标题不能为空。"
    if not content:
        return "记忆内容不能为空。"
    try:
        msg = memory_store.save_memory(name, content)
    except Exception as exc:  # noqa: BLE001
        return f"记忆写入失败：{exc}"
    return f"✓ 已写入记忆：{msg}"
