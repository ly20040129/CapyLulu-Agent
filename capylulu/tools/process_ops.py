"""进程管理工具（批次8）：列出进程 / 结束进程（含系统关键进程白名单保护）。

process_list 走 PowerShell Get-Process；process_kill 走 Stop-Process，
执行前必须校验目标不在系统关键进程白名单内，且 PID >= 100 才允许。
"""
from __future__ import annotations

import subprocess

from .registry import tool

# 系统关键进程白名单：任何情况下都拒绝结束
PROTECTED_PROCESSES = {
    "system", "registry", "smss", "csrss", "wininit", "winlogon",
    "services", "lsass", "lsm", "svchost", "explorer", "dwm", "fontdrvhost",
    "spoolsv", "sihost", "taskhostw", "runtimebroker", "securityhealthservice",
    "audiodg", "searchindexer", "ctfmon", "winlogon",
}

PROTECTED_PID_THRESHOLD = 100  # PID < 100 视为系统核心进程

_POWERSHELL = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]


def _run_ps(script: str) -> str:
    """执行 PowerShell 脚本并返回 stdout。"""
    try:
        r = subprocess.run(_POWERSHELL + [script], capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip()
        if r.returncode != 0 and not out:
            return f"执行失败：{(r.stderr or '').strip()}"
        return out
    except subprocess.TimeoutExpired:
        return "执行超时"
    except Exception as exc:  # noqa: BLE001
        return f"执行异常：{exc}"


@tool(
    name="process_list",
    description="列出当前进程（进程名 / PID / 内存占用 / 主窗口标题），可按名称关键字过滤",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "进程名关键字过滤（如 'chrome'），留空列出全部"},
            "limit": {"type": "integer", "description": "最多返回条数，默认 50"},
        },
        "required": [],
    },
    risk="low",
)
def process_list(keyword: str = "", limit: int = 50) -> str:
    lim = max(1, min(int(limit or 50), 200))
    kw = (keyword or "").strip()
    script = (
        "$p = Get-Process | Select-Object ProcessName, Id, "
        "@{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,1)}}, MainWindowTitle; "
        "if ($p -isnot [array]) { $p = @($p) }; "
    )
    if kw:
        script += f"$p = $p | Where-Object {{ $_.ProcessName -like '*{kw}*' }}; "
    script += (
        f"$p | Sort-Object ProcessName | Select-Object -First {lim} | "
        "Format-Table -AutoSize | Out-String -Width 220"
    )
    out = _run_ps(script)
    if not out or out.startswith("执行"):
        return out or "未获取到进程信息"
    return f"进程列表（匹配「{kw}」最多 {lim} 条）：\n{out}"


@tool(
    name="process_kill",
    description="结束指定进程（按 PID 或进程名）。受系统关键进程白名单保护，explorer/svchost 等一律拒绝",
    parameters={
        "type": "object",
        "properties": {
            "pid": {"type": "integer", "description": "进程 PID（与 name 二选一，优先）"},
            "name": {"type": "string", "description": "进程名（如 'notepad'，无需 .exe 后缀）"},
        },
        "required": [],
    },
    risk="high",
)
def process_kill(pid: int | None = None, name: str = "") -> str:
    # 1. 确定目标
    target_pid = None
    target_name = ""
    if pid:
        target_pid = int(pid)
    if name:
        target_name = name.strip().lower().removesuffix(".exe")
    if not target_pid and not target_name:
        return "请提供 pid 或 name 参数"

    # 2. 若按名杀，先解析出实际 PID 并核验进程真实存在
    if target_pid is None:
        script = (
            "$p = Get-Process -Name '" + target_name + "' -ErrorAction SilentlyContinue; "
            "if ($p) { $p | Select-Object -First 1 -ExpandProperty Id }"
        )
        out = _run_ps(script).strip()
        if not out.isdigit():
            return f"未找到进程：{name}"
        target_pid = int(out)

    # 3. 白名单保护校验
    if target_pid < PROTECTED_PID_THRESHOLD:
        return f"拒绝结束进程：PID {target_pid} 属于系统核心进程（PID < {PROTECTED_PID_THRESHOLD}），已保护"
    script = (
        "$p = Get-Process -Id " + str(target_pid) + " -ErrorAction SilentlyContinue; "
        "if ($p) { $p.ProcessName.ToLower() }"
    )
    out = _run_ps(script).strip().lower()
    if not out:
        return f"进程不存在或已退出：PID {target_pid}"
    real_name = out.splitlines()[0]
    if real_name in PROTECTED_PROCESSES:
        return f"拒绝结束进程：{real_name} 在系统关键进程白名单中，已保护"

    # 4. 执行结束
    script = (
        "$p = Get-Process -Id " + str(target_pid) + " -ErrorAction SilentlyContinue; "
        "if (-not $p) { 'already_gone' } else { Stop-Process -Id " + str(target_pid) +
        " -Force -ErrorAction Stop; 'killed' }"
    )
    out = _run_ps(script).strip()
    if out == "killed":
        return f"已结束进程：{real_name} (PID {target_pid})"
    if out == "already_gone":
        return f"进程已退出：PID {target_pid}"
    return f"结束失败：{out}"
