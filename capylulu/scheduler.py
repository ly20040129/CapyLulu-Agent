"""本地自动化调度器：daemon 线程轮询启用任务，到点生成便签 + 弹系统通知。

- 便签文件写入 <data_dir>/notes/（md，UTF-8 中文），内容含触发时间 + 任务原文；
- 执行结果写入 task_logs.json；
- 通知优先 winotify，其次 PowerShell 弹窗，最后 tkinter 简洁弹窗兜底；
- 线程以 daemon 常驻，app 启动时自动开启，空闲 sleep 不空转；
- 本模块只做调度，不启动服务 / 不占端口 / 不杀进程 / 不改系统关键项。
"""
from __future__ import annotations

import datetime
import re
import threading
import time
from pathlib import Path

from . import tasks
from .config import config

_scheduler_thread: threading.Thread | None = None
_running = False
_errors: list[str] = []


# ---- 通知 ----

def _notify(title: str, message: str) -> str:
    """尝试多种通知方式，返回实际使用的方式描述。"""
    try:
        from winotify import Notification  # 优先系统 Toast

        toast = Notification(
            app_id="Capylulu · 噜噜",
            title=title,
            msg=message,
            duration="long",
        )
        toast.show()
        return "winotify 系统通知"
    except Exception:  # noqa: BLE001
        pass
    try:
        used = _powershell_popup(title, message)
        if used:
            return used
    except Exception:  # noqa: BLE001
        pass
    try:
        _tkinter_popup(title, message)
        return "tkinter 弹窗"
    except Exception:  # noqa: BLE001
        pass
    return "通知发送失败（无可用通道）"


def _powershell_popup(title: str, message: str) -> str | None:
    """PowerShell MessageBox 弹窗（不依赖第三方模块）。"""
    import subprocess

    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.MessageBox]::Show("
        f"'{(message or '').replace(chr(39), chr(39)+chr(39))}', "
        f"'{(title or '').replace(chr(39), chr(39)+chr(39))}', 'OK', 'Information')"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, timeout=10, check=False,
    )
    if proc.returncode == 0:
        return "PowerShell 弹窗"
    return None


def _tkinter_popup(title: str, message: str) -> None:
    """tkinter 简洁弹窗兜底。"""
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(title, message)
    root.destroy()


# ---- 便签 ----

def write_note(text: str, ts: str) -> Path:
    """生成便签 md 文件，返回路径。"""
    notes_dir = tasks.NOTES_DIR
    notes_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|\r\n]+', "_", text)[:40] or "便签"
    p = notes_dir / f"{ts[:10]}_{safe}.md"
    idx = 1
    while p.exists():
        p = notes_dir / f"{ts[:10]}_{safe}_{idx}.md"
        idx += 1
    p.write_text(
        f"# 🗒 便签\n\n"
        f"- 触发时间：{ts}\n"
        f"- 任务内容：{text}\n\n"
        f"---\n\n{text}\n",
        encoding="utf-8",
    )
    return p


# ---- 调度 ----

def _execute(item: dict, triggered: datetime.datetime) -> None:
    """执行一个到期任务：便签 + 通知 + 写日志。"""
    text = item.get("text", "")
    action = item.get("action", "both")
    ts = triggered.strftime("%Y-%m-%d %H:%M:%S")
    results: list[str] = []
    note_path = None
    if action in ("note", "both"):
        try:
            note_path = write_note(text, ts)
            results.append(f"便签已生成：{note_path.name}")
        except Exception as exc:  # noqa: BLE001
            results.append(f"便签生成失败：{exc}")
    if action in ("remind", "both"):
        used = _notify("⏰ 噜噜的定时提醒", f"到点啦：{text}")
        results.append(used)
    tasks.log_event_raw(text, ts, "；".join(results) or "已执行", note=str(note_path) if note_path else "")


def _tick() -> None:
    """检查一轮：只处理最早到期的一个任务，避免积压连弹。"""
    now = datetime.datetime.now()
    items = tasks.load()
    due: list[tuple[int, dict, datetime.datetime]] = []
    for idx, item in enumerate(items):
        if not item.get("enabled", True):
            continue
        nxt = item.get("next") or ""
        if not nxt:
            continue
        try:
            nxt_dt = datetime.datetime.strptime(nxt, "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if now >= nxt_dt:
            due.append((idx, item, nxt_dt))
    if not due:
        return
    due.sort(key=lambda x: x[2])
    idx, item, nxt_dt = due[0]
    _execute(item, nxt_dt)
    if item.get("kind") == "once":
        item["enabled"] = False
        item["next"] = ""
    else:
        nxt2 = tasks.next_trigger(item, now)
        item["next"] = nxt2.strftime("%Y-%m-%d %H:%M") if nxt2 else ""
    tasks.save(items)


def _scheduler_loop(stop_event: threading.Event) -> None:
    global _running
    while not stop_event.is_set():
        try:
            _tick()
        except Exception as exc:  # noqa: BLE001
            _errors.append(f"{time.strftime('%H:%M:%S')} {exc}")
            if len(_errors) > 20:
                _errors.pop(0)
        stop_event.wait(15)  # 空闲 sleep，不空转
    _running = False


def start() -> str:
    """启动调度线程（幂等）。"""
    global _scheduler_thread, _running
    if _running and _scheduler_thread and _scheduler_thread.is_alive():
        return "调度器已在运行"
    stop_event = threading.Event()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop, args=(stop_event,),
        name="capylulu-scheduler", daemon=True,
    )
    _scheduler_thread._capylulu_stop = stop_event  # noqa: SLF001
    _running = True
    _scheduler_thread.start()
    return "调度器已启动（daemon 常驻，空闲每 15 秒检查一次）"


def stop() -> str:
    """停止调度线程。"""
    global _running
    t = _scheduler_thread
    if t and t.is_alive() and hasattr(t, "_capylulu_stop"):
        t._capylulu_stop.set()  # noqa: SLF001
        t.join(timeout=3)
    _running = False
    return "调度器已停止"


def is_running() -> bool:
    return bool(_running and _scheduler_thread and _scheduler_thread.is_alive())


def status_text() -> str:
    """自动任务页状态行。"""
    items = tasks.load()
    enabled = [i for i in items if i.get("enabled", True) and i.get("next")]
    state = "🟢 运行中" if is_running() else "🔴 未运行"
    lines = [f"调度器：{state} · 启用任务 {len(enabled)} 个"]
    if enabled:
        nxt_item = min(enabled, key=lambda i: i.get("next") or "9999-99-99 99:99")
        lines.append(f"最近触发：**{nxt_item['next']}** · {nxt_item.get('text', '')[:24]}")
    if _errors:
        lines.append(f"最近错误：{_errors[-1]}")
    return "\n".join(lines)
