"""自动任务引擎：加载/保存/执行自动任务（module.func + cron）。

自动任务条目字段：{name, cron, module, func, params, enabled, created, next}。
执行前白名单校验 + 本地文件锁防重入；结果写 task_logs.json 并弹通知。
"""
from __future__ import annotations

import importlib
import inspect
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

from . import tasks
from .config import config
from .cron_parser import next_after, parse_cron

AUTO_LOG_TAG = "[TaskEngine]"
LOCK_SECONDS = 60  # 锁窗口：60 秒内视为已执行过，防重入

LOCKS_DIR = config.data_dir / "locks"  # 自动任务防重入锁目录（中间数据，不清理）


def refresh_paths() -> None:
    """数据目录迁移后刷新锁目录路径。"""
    global LOCKS_DIR
    LOCKS_DIR = config.data_dir / "locks"


# ---- 白名单（安全关键） ----

def _build_allowed() -> set[str]:
    """构建白名单：capylulu.tools.* 注册函数 + skills.runtime.run_skill。

    只允许经 tools/registry.py 注册的工具函数，白名单之外执行前直接拒绝。
    """
    allowed = {"capylulu.skills.runtime.run_skill"}
    from .tools.registry import registered_names  # 延迟导入避免循环

    names = set(registered_names())
    tools_dir = Path(__file__).resolve().parent / "tools"
    for mod_file in sorted(tools_dir.glob("*.py")):
        if mod_file.name in ("__init__.py", "registry.py"):
            continue
        mod_name = f"capylulu.tools.{mod_file.stem}"
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[TaskEngine] 白名单模块导入失败：{mod_name} ({exc})")
            continue
        for fname, obj in vars(mod).items():
            if fname in names and inspect.isfunction(obj):
                allowed.add(f"{mod_name}.{fname}")
    return allowed


ALLOWED_FUNCS: set[str] = _build_allowed()  # 启动时构建白名单


def refresh_allowed() -> None:
    """动态工具变化（MCP 热接入等）后重建白名单。"""
    global ALLOWED_FUNCS
    ALLOWED_FUNCS = _build_allowed()


# ---- 自动任务清单 ----

def load_auto_tasks() -> list[dict]:
    """从 tasks.load() 过滤自动任务条目。"""
    return [i for i in tasks.load() if tasks.is_auto(i)]


def _next_text(cron: str, now: datetime | None = None) -> str:
    """按 cron 计算下次触发文本；cron 非法抛 ValueError。"""
    nxt = next_after(parse_cron(cron), now or datetime.now())
    return nxt.strftime("%Y-%m-%d %H:%M") if nxt else ""


def _validate_steps(steps) -> str:
    """校验多步脚本 steps 合法性；返回 "" 表示合法，否则返回错误文案。

    steps 为 [{module, func, params, desc}, ...]：每步必须落在白名单，
    函数名可容错修正（同 parse_nl 逻辑）。
    """
    if not steps:
        return ""
    if not isinstance(steps, list) or not steps:
        return "错误：steps 必须是非空数组"
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            return f"错误：第{i + 1}步不是对象"
        goal = str(st.get("goal") or "").strip()
        stype = str(st.get("type") or "").strip()
        if stype == "agentic" or (goal and not st.get("module") and not st.get("func")):
            if not goal:
                return f"错误：第{i + 1}步 agentic 步骤缺少 goal"
            st.setdefault("type", "agentic")
            st.setdefault("max_steps", 8)
            st.setdefault("desc", "")
            continue
        smod = str(st.get("module") or "").strip()
        sfunc = str(st.get("func") or "").strip()
        if not smod or not sfunc:
            return f"错误：第{i + 1}步缺少 module/func"
        full = f"{smod}.{sfunc}"
        if full not in ALLOWED_FUNCS:
            cands = [f for f in ALLOWED_FUNCS if f.rsplit(".", 1)[-1] == sfunc]
            if len(cands) == 1:
                st["module"], st["func"] = cands[0].rsplit(".", 1)
            else:
                return f"错误：第{i + 1}步不在白名单：{full}"
        sparams = st.get("params")
        if sparams is not None and not isinstance(sparams, dict):
            return f"错误：第{i + 1}步 params 必须是对象"
        st.setdefault("params", {})
        st.setdefault("desc", "")
    return ""


def save_auto_task(item: dict) -> str:
    """新增/更新自动任务（按 name 去重），写回 tasks.save()；错误返回"错误：..."。

    支持两种形态：
    - 单步：module + func + params（原有形态）；
    - 多步：steps = [{module, func, params, desc}, ...] 顺序执行（全流程自动化脚本）。
    """
    name = (item.get("name") or "").strip()
    module = (item.get("module") or "").strip()
    func = (item.get("func") or "").strip()
    cron = (item.get("cron") or "").strip()
    steps = item.get("steps") or []
    mode = str(item.get("mode") or "").strip()
    goal = str(item.get("goal") or "").strip()
    if not name:
        return "错误：任务名不能为空"
    if not cron:
        return "错误：cron 不能为空"
    if steps:
        pass
    elif mode == "agentic":
        if not goal:
            return "错误：agentic 模式缺少 goal"
    elif not module or not func:
        return "错误：module 与 func 不能为空（或提供 steps 多步脚本）"
    if steps:
        err = _validate_steps(steps)
        if err:
            return err
    elif mode == "agentic":
        pass  # agentic 步骤不走白名单校验（内部有安全工具子集）
    else:
        full = f"{module}.{func}"
        if full not in ALLOWED_FUNCS:
            return f"错误：模块函数不在白名单：{full}"
    try:
        _next_text(cron)
    except ValueError as exc:
        return f"错误：cron 非法：{exc}"
    now = datetime.now()
    desc = str(item.get("desc") or "").strip()
    payload = {
        "cron": cron,
        "desc": desc,
        "next": _next_text(cron, now),
    }
    if steps:
        payload["steps"] = steps
        payload.pop("module", None)
        payload.pop("func", None)
        payload.pop("params", None)
    elif mode == "agentic":
        payload["mode"] = "agentic"
        payload["goal"] = goal
        payload["max_steps"] = int(item.get("max_steps") or 8)
        payload.pop("module", None)
        payload.pop("func", None)
        payload.pop("params", None)
    else:
        payload["module"] = module
        payload["func"] = func
        payload["params"] = item.get("params") or {}
        payload.pop("steps", None)
    items = tasks.load()
    for it in items:
        if tasks.is_auto(it) and it.get("name") == name:
            it.update(payload)
            tasks.save(items)
            logger.info(f"[TaskEngine] 已更新自动任务：{name}")
            return f"已更新自动任务：{name}"
    new_item = {
        "name": name,
        "enabled": True,
        "created": now.strftime("%Y-%m-%d %H:%M"),
        **payload,
    }
    items.insert(0, new_item)
    tasks.save(items)
    logger.info(f"[TaskEngine] 已保存自动任务：{name}")
    return f"已保存自动任务：{name}"


def remove_auto_task(name: str) -> str:
    """按 name 删除自动任务；不存在返回错误消息。"""
    name = (name or "").strip()
    if not name:
        return "错误：任务名不能为空"
    items = tasks.load()
    for i, it in enumerate(items):
        if tasks.is_auto(it) and it.get("name") == name:
            items.pop(i)
            tasks.save(items)
            logger.info(f"[TaskEngine] 已删除自动任务：{name}")
            return f"已删除自动任务：{name}"
    return f"错误：未找到自动任务：{name}"


def set_auto_enabled(name: str, enabled: bool) -> str:
    """启停自动任务；启用时重算下次触发。"""
    name = (name or "").strip()
    if not name:
        return "错误：任务名不能为空"
    items = tasks.load()
    for it in items:
        if tasks.is_auto(it) and it.get("name") == name:
            it["enabled"] = bool(enabled)
            if enabled:
                try:
                    it["next"] = _next_text(it.get("cron", ""))
                except ValueError as exc:
                    return f"错误：cron 非法：{exc}"
            tasks.save(items)
            logger.info(f"[TaskEngine] 已{'启用' if enabled else '停用'}自动任务：{name}")
            return f"已{'启用' if enabled else '停用'}自动任务：{name}"
    return f"错误：未找到自动任务：{name}"


# ---- 执行 ----

def _lock_path(name: str) -> Path:
    """自动任务锁文件路径（目录自动创建）。"""
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name or "auto")[:60] or "auto"
    return LOCKS_DIR / f"{safe}.lock"


def _acquire_lock(name: str) -> bool:
    """防重入锁：锁文件存在且 mtime 在 60s 内 → 拒绝；否则写锁并放行。"""
    p = _lock_path(name)
    if p.exists():
        try:
            if time.time() - p.stat().st_mtime < LOCK_SECONDS:
                return False
        except OSError:
            pass
    try:
        p.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    except OSError as exc:
        logger.error(f"[TaskEngine] 写锁失败，拒绝执行：{name} ({exc})")
        return False
    return True


def _touch_lock(name: str) -> None:
    """执行结束后刷新锁时间戳，保持防重入窗口。"""
    try:
        _lock_path(name).write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    except OSError as exc:
        logger.error(f"[TaskEngine] 刷新锁失败：{name} ({exc})")


def _log_auto(name: str, summary: str, ok: bool = True) -> None:
    """自动任务执行结果写 task_logs.json（复用 tasks.log_event_raw）。"""
    status = "成功" if ok else "失败"
    tasks.log_event_raw(name or "自动任务", time.strftime("%Y-%m-%d %H:%M:%S"), f"{status}：{summary}")


# ---- 运行状态（供前端轮询展示“运行中”标记）----
# 任务开始执行时登记，每步/每轮更新阶段，结束后清除。纯内存状态，进程重启即空。
_RUNNING: dict[str, dict] = {}


def _mark_running(name: str, phase: str, step: int = 0) -> None:
    """登记任务为运行中，phase 为当前执行阶段（用户可见）。"""
    if not name:
        return
    _RUNNING[name] = {
        "started": time.strftime("%H:%M:%S"),
        "phase": phase,
        "step": step,
    }


def _clear_running(name: str) -> None:
    _RUNNING.pop(name, None)


def running_status() -> list[dict]:
    """当前运行中的自动任务列表（供 /api/tasks/auto/status 轮询）。"""
    return [{"name": n, "started": v["started"], "phase": v["phase"], "step": v["step"]}
            for n, v in sorted(_RUNNING.items())]


# registry wrapper 捕获异常 / 参数缺失校验返回的失败字符串特征。
# 自动任务执行必须据此区分「正常返回」与「工具层失败」，避免把
# "工具执行出错: ..." 误记成成功结果。
_FAIL_TEXT_HINTS = (
    "工具执行出错:", "参数缺失（失败）", "未知工具:",
    "暂不支持", "不支持打开", "未能找到应用", "未找到应用", "无法启动",
    # GUI / 浏览器自动化失败特征：找不到窗口/控件/快照过期/编号越界等必须判失败，
    # 否则 ui_click / window_focus 等“找不到目标”会被误记为成功（假执行）。
    "未找到标题包含", "未找到名为", "控件已失效", "控件快照已过期",
    "未获取到前台窗口", "编号 超出范围", "未安装 uiautomation",
    "页面加载失败", "导航失败", "浏览器实例未启动",
)


def _is_failed_text(text: str) -> bool:
    """判断工具返回文本是否为失败结果（registry 层失败特征）。"""
    return any(h in text for h in _FAIL_TEXT_HINTS)


# 自动补参时允许 LLM 调用的只读检索工具白名单。
# 刻意不含写文件 / 删除 / 移动 / 启动等有副作用工具，防止补参循环里触发破坏性操作。
_FILL_PROBE_TOOLS = (
    "list_dir", "search_files", "read_file", "search_text",
    "now_datetime", "system_info", "disk_usage", "list_desktop",
    "list_installed_apps",
)


# 缺参自修复时禁止 LLM 重选的函数：状态依赖 / 破坏性 / 需前置操作的工具一律排除，
# 防止 LLM 根据一句自然语言描述误选造成不可预期副作用。
# 注意：仅限制"重选"，用户/前端已配置的当前函数不受影响。
_RESELECT_BLOCKED = {
    "process_kill", "window_close",
    "key_simulate", "type_text", "mouse_click", "mouse_scroll", "ui_click",
    "mcp_call_tool", "mcp_tool_list",
    "evolve_improve", "evolve_lesson", "evolve_reflect",
    "memory_write", "skill_create",
    "browser_open", "browser_close", "browser_goto", "browser_click", "browser_fill",
    "browser_press", "browser_extract", "browser_inspect", "browser_screenshot",
    "browser_wait", "browser_download",
}


def _reselect_candidates() -> list[str]:
    """缺参自修复的候选函数清单：白名单 - run_skill - 危险/状态依赖工具。"""
    from .tools.registry import get_tool_schemas  # 延迟导入避免循环

    cands = []
    for full in sorted(ALLOWED_FUNCS):
        fname = full.rsplit(".", 1)[-1]
        if full == "capylulu.skills.runtime.run_skill" or fname in _RESELECT_BLOCKED:
            continue
        sch = get_tool_schemas([fname])
        desc = (sch[0]["function"].get("description") or "") if sch else ""
        cands.append(f"{full}：{desc or '(无说明)'}")
    return cands


def _try_fix_task(name: str, full: str, params: dict, note: str = "",
                  allow_reselect: bool = False) -> tuple[str, dict | None, str]:
    """缺参自修复：LLM 判断当前函数是否匹配任务描述，补齐所选函数的必填参数。

    allow_reselect=False（默认，执行路径一律如此）：当前函数与任务描述不匹配时
    **禁止改选其它函数**，直接返回失败原因，避免“打开钉钉发消息”被降级成
    “只启动应用就标成功”的假执行；用户需重新配置任务（推荐一句话创建拆多步）。
    allow_reselect=True：仅保留给确有需要的内部场景（当前无调用方使用）。

    返回 (chosen_full, filled, reason)：成功时 filled 为完整参数、reason 为空串；
    失败时 chosen_full 保持原函数、filled 为 None、reason 为失败原因（用户可见，禁止静默放弃）。
    仅允许调用 _FILL_PROBE_TOOLS 内的只读工具，绝不放开写类工具。
    """
    if not config.llm_config.get("api_key"):
        return full, None, "未配置 LLM（请先在设置里填写 API Key）"
    func = full.rsplit(".", 1)[-1] if "." in full else full  # 从 full 拆出函数名供 schema 查询
    try:
        from .llm import create_llm  # 延迟导入避免顶层依赖
        from .tools.registry import call_tool, get_tool_schemas, registered_names  # 延迟导入避免循环

        probe_schemas = get_tool_schemas(list(_FILL_PROBE_TOOLS))
        if not probe_schemas:
            return full, None, "只读检索工具 schema 为空，无法自修复"
        candidates = _reselect_candidates()
        if not candidates:
            return full, None, "候选函数清单为空，无法自修复"
        cand_lines = "\n".join(candidates)
        if allow_reselect:
            reselect_rule = ("2. 若明显不匹配，从候选函数中重选一个最能完成任务的；匹配则保留当前函数；\n")
        else:
            reselect_rule = ("2. 若明显不匹配，**禁止改选其它函数**：仍输出原函数且 params 留空，"
                             "让任务按失败处理并提示用户重新配置；匹配则保留当前函数；\n")
        system = (
            "你是 capylulu 自动任务的自修复助手。自动任务执行时参数缺失，且配置的函数可能与"
            "任务描述不匹配（普通用户不知道函数名，只会写自然语言描述）。\n"
            "你的任务：\n"
            "1. 判断当前配置函数是否与任务描述匹配；\n"
            + reselect_rule +
            "3. 为最终选定的函数补齐全部必填参数。\n"
            f"候选函数清单（full 只能从这里面选）：\n{cand_lines}\n"
            "取值规则：任务描述 / 已有参数中已明确给出的值（路径、内容、文件名等）必须原样直接使用，"
            "无需检索确认；仅当某个参数确实无法从描述推断时，才调用只读检索工具查证，"
            "查不到就如实说明，严禁编造。\n"
            f"可调用只读工具：{'、'.join(_FILL_PROBE_TOOLS)}。禁止调用除上述之外的任何工具。\n"
            "注意：Windows 路径在 JSON 中必须双反斜杠转义（如 C:\\\\dir\\\\file.txt）。\n"
            "最终只输出 JSON（不要多余文字）：{\"full\": \"module.func\", \"params\": {完整参数对象}}。"
        )
        user = (
            f"任务名：{name}\n当前配置函数：{full}\n任务描述：{note or '(无)'}\n"
            f"当前已有参数：{json.dumps(params, ensure_ascii=False)}\n"
            "请先判断函数是否匹配，再输出最终 full 与完整 params。"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        llm = create_llm()
        last_content = ""
        for _ in range(8):  # 最多 8 轮：工具调用 + JSON 解析纠错 + 缺参补齐
            resp = llm.chat(messages, tools=probe_schemas)
            tcs = resp.get("tool_calls") or []
            if tcs:
                assistant_msg = {"role": "assistant", "content": resp.get("content") or ""}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in tcs
                ]
                messages.append(assistant_msg)
                for tc in tcs:
                    tool_name = tc["function"]["name"]
                    if tool_name not in _FILL_PROBE_TOOLS:  # 越界工具直接拒绝
                        messages.append({"role": "tool", "tool_call_id": tc["id"],
                                         "content": f"禁止调用工具：{tool_name}"})
                        continue
                    raw = tc["function"].get("arguments")
                    try:
                        args = json.loads(raw) if isinstance(raw, str) and raw else {}
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    if not isinstance(args, dict):
                        args = {}
                    result = call_tool(tool_name, args)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})
                continue
            data = _extract_json(resp.get("content") or "")
            if not data or not isinstance(data.get("params"), dict):
                # JSON 解析失败：把原文回喂让 LLM 重新输出，而非直接放弃
                last_content = str(resp.get("content") or "")[:200]
                messages.append({"role": "user",
                                 "content": "上一条回复不是合法 JSON，请只输出 {\"full\": ..., \"params\": {...}} 形式的 JSON。"})
                continue
            chosen = (data.get("full") or "").strip()
            if chosen not in ALLOWED_FUNCS:
                messages.append({"role": "user",
                                 "content": f"函数 {chosen} 不在候选白名单，请从候选函数清单中选择一个 full。"})
                continue
            if not allow_reselect and chosen != full:
                # 单步/多步执行路径禁止自动改选函数：函数与描述不匹配即如实失败，
                # 避免“打开钉钉发消息”被降级成“只启动应用就标成功”的假执行。
                return full, None, (
                    f"配置的函数 {full} 与任务描述不匹配（LLM 判定应使用 {chosen}）。"
                    "为避免假执行，任务已按失败处理：请在任务列表重新配置（推荐用“一句话创建”，"
                    "让系统拆解为多步 UI 流程），或在函数下拉框选用与描述一致的函数。"
                )
            if chosen != full and (chosen == "capylulu.skills.runtime.run_skill"
                                   or chosen.rsplit(".", 1)[-1] in _RESELECT_BLOCKED):
                messages.append({"role": "user",
                                 "content": f"函数 {chosen} 属于危险/状态依赖工具，禁止重选，请换一个安全候选函数。"})
                continue
            filled = {**params, **data["params"]}
            ch_func = chosen.rsplit(".", 1)[-1]
            required = []
            if ch_func in registered_names():
                ch_schemas = get_tool_schemas([ch_func])
                if ch_schemas:
                    ps = ch_schemas[0]["function"].get("parameters") or {}
                    required = list(ps.get("required") or [])
            missing = [k for k in required if k not in filled]
            if missing:
                # 仍缺必填项：回喂缺失清单让 LLM 补齐后再输出
                messages.append({"role": "user",
                                 "content": f"你输出的参数仍缺少必填项：{', '.join(missing)}，"
                                             "请补齐后重新输出完整 JSON。"})
                continue
            return chosen, filled, ""
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[TaskEngine] 缺参自修复失败：{name} ({exc})")
        return full, None, f"LLM 调用异常：{exc}"
    return full, None, f"多轮修复后仍未得到完整参数（最后回复：{last_content or '(空)'}）"


def _exec_one_step(name: str, full: str, params: dict, desc: str = "") -> tuple[bool, str, str]:
    """执行单个白名单调用（含缺参自修复）；返回 (ok, result_text, error)。"""
    module, func = full.rsplit(".", 1)
    if full not in ALLOWED_FUNCS:
        return False, "", f"模块函数不在白名单：{full}"
    try:
        mod = importlib.import_module(module)
        fn = getattr(mod, func, None)
    except Exception as exc:  # noqa: BLE001
        return False, "", f"模块导入失败：{exc}"
    if not callable(fn):
        return False, "", f"函数不存在或不可调用：{full}"
    try:
        # 优先走 registry.call_tool：统一参数缺失校验与异常包装，避免直接 fn(**params)
        # 绕过校验；且 call_tool 的 wrapper 会捕获异常返回失败字符串，而非抛给调度器。
        from .tools.registry import call_tool, registered_names  # 延迟导入避免循环

        if func in registered_names():
            raw = call_tool(func, params)
        else:  # run_skill 等未注册进 registry 的白名单函数走原路径
            raw = fn(**params)
        result_text = str(raw) if raw is not None else "(无返回)"
        # 参数缺失失败时尝试 LLM 自修复（可重选匹配函数 + 补全参数）后重试一次
        if _is_failed_text(result_text) and "参数缺失" in result_text:
            chosen_full, filled, fill_reason = _try_fix_task(name, full, params, desc, allow_reselect=False)
            if filled is not None:
                new_func = chosen_full.rsplit(".", 1)[-1]
                logger.info(f"[TaskEngine] {name} 缺参自修复：{full} -> {chosen_full} 补参 {filled}")
                try:
                    if new_func in registered_names():
                        retry = call_tool(new_func, filled)
                    else:  # run_skill 等未注册函数
                        mod2 = importlib.import_module(chosen_full.rsplit(".", 1)[0])
                        fn2 = getattr(mod2, new_func, None)
                        retry = fn2(**filled) if callable(fn2) else f"函数不存在或不可调用：{chosen_full}"
                except Exception as exc:  # noqa: BLE001
                    retry = f"执行异常：{exc}"
                retry_text = str(retry) if retry is not None else "(无返回)"
                if not _is_failed_text(retry_text):
                    result_text = f"[已自动补参] {retry_text}"
                else:
                    result_text = retry_text
            else:
                # 自修复失败必须让用户看到原因，不能静默落回原始报错
                result_text = f"{result_text}（LLM 自补参未成功：{fill_reason}）"
        if _is_failed_text(result_text):
            return False, result_text, result_text
        return True, result_text, ""
    except Exception as exc:  # noqa: BLE001
        return False, "", f"执行异常：{exc}"


# ---- Agentic 模式（装脑）：LLM 自主循环，观察 -> 决策 -> 操作 -> 校验 ----
# 参考 cowagent 的 Agent 循环：界面快照编号化后由 LLM 按编号决策。
# 安全约束：LLM 只能调用下列『UI 自动化闭环』工具，删除/写文件/系统/记忆等一律排除。
_AGENTIC_TOOLS = (
    "launch_app", "window_focus", "window_inspect", "ui_click", "ui_click_ref",
    "ui_observe", "ui_click_text", "send_chat_message", "type_text", "mouse_click", "mouse_scroll", "screenshot",
    "browser_open", "browser_goto", "browser_inspect", "browser_click",
    "browser_click_ref", "browser_fill", "browser_press", "browser_wait",
    "browser_extract", "browser_screenshot", "browser_close",
)


def _agentic_allowed_map() -> dict[str, str]:
    """agentic 可用工具短名 -> 全名（capylulu.tools.*.func）映射。"""
    m = {}
    for full in ALLOWED_FUNCS:
        f = full.rsplit(".", 1)[-1]
        if f in _AGENTIC_TOOLS:
            m[f] = full
    return m


# 常见本地桌面应用关键词：goal 命中时必须走 launch_app，禁止 LLM 用浏览器打开网页版
_LOCAL_APP_HINTS = ("钉钉", "微信", "wechat", "qq", "企业微信", "飞书", "wps", "word", "excel",
                    "ppt", "outlook", "teams", "网易云", "qq音乐", "steam", "bilibili", "哔哩哔哩",
                    "抖音", "快手", "淘宝", "京东", "阿里旺旺", "photoshop", "ps", "vscode", "idea", "pycharm")

# 验证类工具：声明完成前的最后一步必须是其中之一，防止点击/键入成功即假报完成
_VERIFY_TOOLS = ("ui_observe", "screenshot", "window_inspect", "browser_extract", "browser_screenshot", "browser_inspect")

# 视觉优先的复杂自绘应用：UIA 拿不到语义名称，必须走 ui_observe 视觉观察
_VISION_FIRST_APPS = ("钉钉", "微信", "企业微信", "飞书", "qq音乐", "网易云音乐")

# UIA 失败特征串：命中时自动提示 LLM 切换视觉观察
_UIA_FAIL_HINTS = ("未找到名为", "超出范围", "未找到标题", "缺少语义", "快照过期")


def _extract_local_app(goal: str) -> str | None:
    """从目标文本中提取应优先本地启动的应用名；未命中返回 None。"""
    g = (goal or "").strip()
    alias = {
        "钉钉": "钉钉", "微信": "微信", "企业微信": "企业微信", "飞书": "飞书",
        "word": "Word", "excel": "Excel", "ppt": "PowerPoint", "wps": "WPS",
        "outlook": "Outlook", "teams": "Teams", "qq": "QQ", "qq音乐": "QQ音乐",
        "网易云": "网易云音乐", "steam": "Steam", "bilibili": "哔哩哔哩", "哔哩哔哩": "哔哩哔哩",
        "抖音": "抖音", "快手": "快手", "淘宝": "淘宝", "京东": "京东",
        "vscode": "Visual Studio Code", "pycharm": "PyCharm", "idea": "IntelliJ IDEA",
    }
    for key in _LOCAL_APP_HINTS:
        if key.lower() in g.lower():
            return alias.get(key, key)
    return None


def _extract_msg_keyword(goal: str) -> str | None:
    """从发消息类目标中提取消息内容关键词（引号内的文本）。

    例如「打开钉钉给罗永发消息：你好」-> 你好；「给张三发消息说"下班了"」-> 下班了。
    没有引号/冒号形式则返回 None（不做内容断言，只做验证工具闸门）。
    """
    import re
    g = (goal or "").strip()
    m = re.search(r"[：:]\s*[\"“]?([^\"”\n]{1,20})[\"”]?$", g)
    if m:
        kw = m.group(1).strip()
        if kw:
            return kw[:12]
    m2 = re.search(r"[\"“]([^\"”]{1,20})[\"”]", g)
    if m2:
        kw = m2.group(1).strip()
        if kw:
            return kw[:12]
    return None


def _exec_agentic_loop(name: str, goal: str, max_steps: int = 8) -> tuple[bool, str, str]:
    """Agent 自主循环：LLM 每轮决定调哪个白名单工具，直到 done 或达到最大步数。

    返回 (ok, result_text, error)。目标为空直接失败。
    """
    goal = (goal or "").strip()
    if not goal:
        return False, "", "agentic 步骤缺少 goal"
    if not config.llm_config.get("api_key"):
        return False, "", "未配置 LLM（请先在设置里填写 API Key）"
    from .llm import create_llm  # 延迟导入避免顶层依赖

    tool_map = _agentic_allowed_map()
    if not tool_map:
        return False, "", "agentic 可用工具为空（白名单构建异常）"
    # 注入工具描述，帮助 LLM 正确选工具（避免凭函数名臆测）
    desc_map = {}
    try:
        from .tools.registry import get_tool_schemas
        for sch in get_tool_schemas(_AGENTIC_TOOLS):
            fn = sch.get("function", {})
            desc_map[fn.get("name", "")] = (fn.get("description") or "").strip()
    except Exception:  # noqa: BLE001
        desc_map = {}
    # 桌面应用任务：从白名单剔除 browser_*，杜绝 LLM 跑偏打开网页版
    forced_app = _extract_local_app(goal)
    if forced_app:
        tool_map = {k: v for k, v in tool_map.items() if not k.startswith("browser_")}
    tool_list = "\n".join(
        f"- {short}: {full}" + (f"（{desc_map.get(short, '')}）" if desc_map.get(short) else "")
        for short, full in sorted(tool_map.items())
    )
    system = (
        "你是 capylulu 的桌面自动化 Agent，任务是完成用户给定的目标，自主决定下一步操作。\n"
        "每轮只能调用一个工具，工具名只能从下列白名单选择，禁止编造：\n" + tool_list + "\n"
        "操作原则：\n"
        "1. 观察界面优先用 window_inspect 获取带编号的控件快照；若返回的可交互控件缺少语义名称"
        "（如复杂应用钉钉/微信/QQ/自绘界面只有 DocumentControl/无名字段），必须改用 ui_observe "
        "做视觉观察，它会返回界面文字元素及其屏幕坐标；\n"
        "2. 桌面点击优先用 ui_click_ref（按编号），但视觉观察得到的坐标用 mouse_click(x,y) 点击；"
        "网页先用 browser_inspect 获取带编号的元素快照，点击用 browser_click_ref，输入用 type_text / browser_fill；\n"
        "3. 不要重复调用结果相同的工具；工具失败时根据错误信息换一种方式；\n"
        "4. 定位目标（如搜索联系人）优先通过界面搜索框输入关键词，而不是盲点列表项；\n"
        "4b. 导航纪律：如果 ui_observe 观察到的不是目标页面（例如看到 AI 助理聊天、文档、表单、团队文件、设置等非消息列表界面），"
        "必须先用 mouse_click 点击界面左侧的「消息」导航项回到消息列表页，再继续定位会话，严禁直接在错误页面输入/发送；\n"
        "4c. ui_observe 返回的坐标已是屏幕绝对坐标，可直接作为 mouse_click 的 x,y 使用；坐标行可能含多余分隔符（如「名称 | 类型 | | 123,456」），以最后的「数字,数字」为准；\n"
        "4d. 操作桌面应用时 ui_observe 必须带 app 参数（如 ui_observe(app='钉钉')），它会先聚焦目标窗口再截屏，禁止空参观察导致截错窗口；\n"
        "4e. 聊天应用（钉钉/微信/QQ）操作指引：界面通常包含顶部搜索框、会话列表区、聊天区（底部是消息输入框）。"
        "给某人发消息的标准动作：先用 ui_click_text 点击顶部搜索框（如 text='搜索'），type_text 输入对方姓名，"
        "再用 ui_click_text 点击搜索结果中的目标联系人（如 text='罗永'）进入会话；"
        "进入会话后，先用 ui_click_text 或 ui_observe 找到聊天区底部「输入框」元素，mouse_click 点击获得焦点，再 type_text 键入内容并回车发送；"
        "若界面停在非会话页（工作台/文档/应用中心等），禁止死磕左侧「消息」导航（新版钉钉可能无此文字），"
        "改用顶部搜索框搜索联系人直达会话；禁止用 ui_click/ui_click_ref 操作自绘应用（它们 UIA 拿不到语义控件，只会失败），一律用 ui_click_text 或视觉坐标 mouse_click；\n"
        "4f. 语义点击优先：需要点击界面上的文字元素时，优先用 ui_click_text(text='元素名', app='目标应用')——它会自动做视觉观察并按名称定位点击"
        "（如 ui_click_text('消息', app='钉钉') 点击左侧「消息」导航，ui_click_text('罗永', app='钉钉') 进入会话，ui_click_text('发送', app='钉钉') 发送），"
        "比手算坐标更可靠；只有语义点击找不到目标时才退回 ui_observe 手动取坐标 mouse_click；\n"
        "4g. 『给XX（应用）的YY（联系人）发消息/回复/发送XX内容』类目标：**必须**调用 send_chat_message(app='XX', contact='YY', message='内容') 一步完成"
        "（它会自动搜索联系人→点击进入会话→聚焦输入框→键入回车→视觉验证，点错候选会验证失败并自动停止，不会误发），"
        "**禁止手动拆 ui_click_text/type_text 步骤**——手动单点没有会话验证，极易点中左侧身份区/头像/导航区，"
        "点击后进入的是个人页/工作台而不是聊天会话，后续键入全部落空且无法发现；\n"
        "若 send_chat_message 返回失败（如未找到联系人/未进入会话），先 ui_observe 看清当前界面，"
        "必要时改用顶部搜索框搜索联系人，然后重试一次 send_chat_message；仍失败就报告失败，禁止改用手动拆解；\n"
        "5. 凡『发消息/发送/回复/发文件』类目标，必须按闭环执行且缺一不可：\n"
        "   a. 先定位目标会话/联系人：确保在消息列表页后，用界面搜索框输入姓名（type_text），或 ui_observe 找到目标行 mouse_click 点击；\n"
        "   b. 确认焦点已进入消息输入框后，再调用 type_text 键入内容并回车；\n"
        "   c. 发送后必须调用 ui_observe 或 screenshot 验证：界面处于目标会话、且聊天窗口出现发送内容，才能标 done=true；\n"
        "   d. 只看到点击/键入成功但未验证界面结果，一律不得标 done=true；\n"
        "   e. 验证未通过时（消息未出现），不要原地重复相同动作，先 ui_observe 看清当前界面，再决定补点输入框/补点发送按钮/重新键入；\n"
        "6. 达到目标后必须结束循环。\n"
        "严格输出 JSON（不要多余文字）：{\"tool\": \"函数名\", \"params\": {参数对象}, \"done\": false, \"summary\": \"这一步做了什么/观察到什么（一句话）\"}\n"
        "当目标已完成或无法继续时输出 {\"done\": true, \"summary\": \"完成情况说明\"}（不带 tool 字段）。"
    )
    history = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"目标：{goal}\n环境：Windows 11 桌面 + Playwright 浏览器（browser_* 自动管理浏览器实例）。开始执行。"},
    ]
    lines = []
    steps = max(int(max_steps or 8), 1)
    last_tool: str | None = None  # 最近一次成功/失败执行过的工具（含强制路由）
    last_verify_text = ""  # 最近一次验证类工具（ui_observe/screenshot 等）的返回文本，用于完成断言
    msg_keyword = _extract_msg_keyword(goal)  # 发送类目标的消息内容关键词（如「你好」），无则 None
    try:
        llm = create_llm()
        # 首步路由：goal 命中本地应用名时，先强制 launch_app，避免 LLM 误走浏览器网页版
        forced_app = _extract_local_app(goal)
        if forced_app:
            ok0, text0, err0 = _exec_one_step(name, tool_map["launch_app"], {"name": forced_app}, "agentic#route")
            r0 = text0 or err0
            last_tool = "launch_app"
            lines.append(f"[启动] launch_app({forced_app}) -> {r0[:200]}")
            history.append({"role": "user", "content": f"（已按目标中的本地应用名强制执行 launch_app('{forced_app}')，结果：{r0[:500]}）请继续：聚焦该窗口并完成目标，不要再打开浏览器网页版。"})
            # 复杂自绘应用：强制先聚焦窗口 + 视觉观察，把观察结果直接注入上下文，避免 LLM 盲点编号
            if any(app in (forced_app or "") for app in _VISION_FIRST_APPS):
                okf, tf, ef = _exec_one_step(name, tool_map["window_focus"], {"title_substr": forced_app}, "agentic#focus")
                rf = tf or ef
                last_tool = "window_focus"
                lines.append(f"[聚焦] window_focus({forced_app}) -> {rf[:200]}")
                history.append({"role": "user", "content": f"（已聚焦 {forced_app} 窗口：{rf[:300]}）"})
                okv, tv, ev = _exec_one_step(name, tool_map["ui_observe"], {"app": forced_app}, "agentic#observe")
                rv = tv or ev
                last_tool = "ui_observe"
                lines.append(f"[观察] ui_observe({forced_app}) -> {rv[:800]}")
                history.append({"role": "user", "content": f"（以下是 ui_observe 对 {forced_app} 的视觉观察结果，必须基于这些元素和坐标用 mouse_click 点击，禁止盲点编号控件）\n{rv[:2000]}"})
        for step_i in range(steps):
            _mark_running(name, f"Agent 循环 第{step_i + 1}/{steps} 轮（决策中）", step_i + 1)
            resp = llm.chat(history, tools=None)
            content = resp.get("content") or ""
            data = _extract_json(content)
            if not data:
                # JSON 解析失败：把原文回喂一次，要求严格 JSON
                lines.append(f"[第{step_i + 1}轮] LLM 返回非 JSON，已回喂重试")
                history.append({"role": "user", "content": f"你上轮输出不是合法 JSON（原文：{content[:400]}）。请只输出严格 JSON，不要多余文字。"})
                resp = llm.chat(history, tools=None)
                content = resp.get("content") or ""
                data = _extract_json(content)
            if not data:
                return False, "\n".join(lines), f"第{step_i + 1}轮 LLM 未返回可解析 JSON（重试后仍失败）"
            if data.get("done"):
                # 硬闸门1：声明完成前，最近一步必须是验证类工具，防止点击/键入成功就假报完成
                if last_tool not in _VERIFY_TOOLS:
                    lines.append(f"[拦截] 尝试直接标 done，但最近一步是 {last_tool or '无'}（非验证工具），请先 ui_observe/screenshot 验证目标真实达成")
                    history.append({"role": "user", "content": "不能直接结束：你还没有用 ui_observe 或 screenshot 验证目标真实达成。请先调用验证工具观察当前界面，确认结果后再决定 done。"})
                    continue
                # 硬闸门2：发送类目标的消息内容断言——验证文本里必须出现消息关键词
                if msg_keyword and msg_keyword not in (last_verify_text or ""):
                    lines.append(f"[拦截] 消息内容「{msg_keyword}」未在最近验证结果中出现，疑似未真实发送")
                    history.append({"role": "user", "content": f"你的验证结果里没有出现消息内容「{msg_keyword}」，说明消息可能还没发出去。请继续操作：确认输入框有内容并回车发送，或重新观察聊天窗口后再判断。"})
                    continue
                summary = str(data.get("summary") or "目标完成")
                # 负向词校验：LLM 自述未完成时不能算成功，避免假成功。
                neg = ("无法完成", "未完成", "失败", "未找到", "未发送", "未能", "找不到", "没有找到", "未能完成")
                if any(w in summary for w in neg):
                    lines.append(f"[失败] {summary}")
                    logger.warning(f"[TaskEngine] {name} agentic 报告未完成：{summary}")
                    return False, "\n".join(lines), f"任务未完成：{summary}"
                lines.append(f"[完成] {summary}")
                logger.info(f"[TaskEngine] {name} agentic 完成：{summary}")
                return True, "\n".join(lines), ""
            tool = str(data.get("tool") or "").strip()
            params = data.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            if tool not in tool_map:
                lines.append(f"[跳过] LLM 选择了白名单外工具：{tool}")
                history.append({"role": "user", "content": f"你选择了白名单外工具 {tool}，请从可用列表换一个。"})
                continue
            # 视觉优先应用下，点击/键入前强制再聚焦目标窗口，防止其他窗口抢占前台导致操作错窗口
            if tool in ("mouse_click", "type_text") and forced_app and any(app in forced_app for app in _VISION_FIRST_APPS):
                okf, tf, ef = _exec_one_step(name, tool_map["window_focus"], {"title_substr": forced_app}, f"agentic#{step_i + 1}#refocus")
                if not okf:
                    lines.append(f"[重聚焦失败] window_focus({forced_app}) -> {ef}")
                    history.append({"role": "user", "content": f"操作前重聚焦 {forced_app} 失败：{ef}。请先解决窗口聚焦问题再操作。"})
                    continue
                last_tool = "window_focus"
                last_verify_text = ""  # 重聚焦后需要重新验证，清空断言缓存
                lines.append(f"[重聚焦] window_focus({forced_app}) -> {(tf or ef)[:150]}")
                history.append({"role": "user", "content": f"（操作前已重新聚焦 {forced_app} 窗口）"})
            ok, text, err = _exec_one_step(name, tool_map[tool], params, f"agentic#{step_i + 1}")
            last_tool = tool
            result_txt = text or err
            if tool in _VERIFY_TOOLS:
                last_verify_text = result_txt
            lines.append(f"[第{step_i + 1}步] {tool}({params}) -> {result_txt[:200]}")
            history.append({"role": "assistant", "content": content[:1500]})
            history.append({"role": "user", "content": f"工具返回：{str(result_txt)[:1500]}"})
            if not ok:
                lines.append(f"[注意] 第{step_i + 1}步失败：{err}，请换一种方式继续")
                # UIA 失败特征：自动提示切换视觉观察，避免 LLM 反复盲试或跑偏浏览器
                if any(h in (err or "") for h in _UIA_FAIL_HINTS):
                    hint = "该应用是自绘界面，UIA 拿不到语义控件。请改用 ui_observe 做视觉观察，用返回的坐标 mouse_click 点击，禁止再盲点 ui_click_ref 编号或打开浏览器。"
                    history.append({"role": "user", "content": hint})
                    lines.append(f"[提示] {hint}")
        return False, "\n".join(lines), f"达到最大步数 {steps} 仍未完成"
    except Exception as exc:  # noqa: BLE001
        return False, "\n".join(lines), f"agentic 执行异常：{exc}"


def _exec_step_sequence(name: str, steps: list) -> tuple[bool, str, str]:
    """顺序执行多步脚本；任一步失败立即中止；type=agentic 步骤走 LLM 自主循环。

    返回 (ok, result_text, error)。
    """
    lines = []
    for i, st in enumerate(steps):
        smod = str(st.get("module") or "").strip()
        sfunc = str(st.get("func") or "").strip()
        desc = str(st.get("desc") or "").strip()
        sparams = st.get("params") or {}
        if not isinstance(sparams, dict):
            sparams = {}
        goal = str(st.get("goal") or "").strip()
        stype = str(st.get("type") or "").strip()
        _mark_running(name, f"第{i + 1}/{len(steps)} 步：{desc or sfunc}", i + 1)
        if stype == "agentic" or (goal and not smod and not sfunc):
            ok, text, err = _exec_agentic_loop(name, goal, int(st.get("max_steps") or 8))
            label = f"第{i + 1}步（Agent 自主）" + (f"（{desc}）" if desc else "")
            if not ok:
                logger.error(f"[TaskEngine] {name} {label}失败：{err}")
                return False, "", f"{label}失败：{err}"
            lines.append(f"{label}：{text}")
            continue
        ok, text, err = _exec_one_step(name, f"{smod}.{sfunc}", sparams, desc)
        label = f"第{i + 1}步" + (f"（{desc}）" if desc else "")
        if not ok:
            logger.error(f"[TaskEngine] {name} {label}失败：{err}")
            return False, "", f"{label}失败：{err}"
        lines.append(f"{label}：{text}")
    return True, "\n".join(lines), ""


def execute_auto(item: dict) -> dict:
    """执行单个自动任务：防重入锁 → 白名单校验 → importlib 调用 → 写历史 → 通知。

    支持单步（module+func+params）与多步（steps 顺序执行，任一步失败即中止）。
    返回 {"ok": bool, "result": str, "error": str, "used_ms": int}。
    """
    name = (item.get("name") or "").strip()
    module = (item.get("module") or "").strip()
    func = (item.get("func") or "").strip()
    params = item.get("params") or {}
    steps = item.get("steps") or []
    if not isinstance(params, dict):
        params = {}
    started = time.time()

    # 1. 防重入锁：60s 内已执行过则跳过
    if not _acquire_lock(name):
        msg = "任务在 60 秒内已执行过，跳过（防重入）"
        logger.warning(f"[TaskEngine] {name} {msg}")
        _log_auto(name, msg, ok=False)
        return {"ok": False, "result": "", "error": msg, "used_ms": 0}

    ok = True
    result_text = ""
    error = ""
    try:
        _mark_running(name, "启动中", 0)
        # 2. 多步脚本：顺序执行 steps，任一步失败立即中止
        if steps:
            ok, result_text, error = _exec_step_sequence(name, steps)
            if not ok:
                logger.error(f"[TaskEngine] {name} 执行失败：{error}")
            return {"ok": ok, "result": result_text, "error": error,
                    "used_ms": int((time.time() - started) * 1000)}
        # 2.5 Agentic 模式：LLM 自主循环完成目标
        if str(item.get("mode") or "").strip() == "agentic":
            ok, result_text, error = _exec_agentic_loop(
                name, str(item.get("goal") or "").strip(), int(item.get("max_steps") or 8)
            )
            if not ok:
                logger.error(f"[TaskEngine] {name} agentic 执行失败：{error}")
            return {"ok": ok, "result": result_text, "error": error,
                    "used_ms": int((time.time() - started) * 1000)}
        # 3. 单步：白名单校验 + importlib 调用（含缺参自修复）
        ok, result_text, error = _exec_one_step(name, f"{module}.{func}", params, item.get("desc") or "")
        if not ok:
            logger.error(f"[TaskEngine] {name} 执行失败：{error}")
    finally:
        # 4. 结果写 task_logs.json，并清除运行中标记
        used_ms = int((time.time() - started) * 1000)
        _log_auto(name, result_text or error, ok=ok)
        _clear_running(name)
        _touch_lock(name)

    # 5. 通知摘要（默认开启；notify=false 只写日志不弹窗）。
    # 放后台 daemon 线程，避免无人值守时弹窗阻塞调度线程。
    if item.get("notify", True):
        try:
            from .scheduler import _notify  # 延迟导入避免循环

            summary = f"{name}：{result_text or error}"
            threading.Thread(
                target=_notify,
                args=("🤖 噜噜的自动任务", summary[:120]),
                daemon=True,
            ).start()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[TaskEngine] 通知发送失败：{exc}")

    return {"ok": ok, "result": result_text, "error": error, "used_ms": used_ms}


# ---- 自然语言拆解 ----

def _extract_json(content: str) -> dict | None:
    """从 LLM 返回文本中提取 JSON 对象（容忍 ```json 围栏与前后杂文）。"""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_nl(text: str) -> dict:
    """自然语言 → 任务定义建议（不落盘，供前端确认）。

    调 llm client 单次 chat，要求输出 JSON：{name, cron, module, func, params, note}。
    解析失败返回 {"ok": False, "error": ...}，绝不编造。
    """
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "任务描述不能为空"}
    if not config.llm_config.get("api_key"):
        return {"ok": False, "error": "未配置 LLM（请先在设置里填写 API Key）"}
    from .llm import create_llm  # 延迟导入，避免顶层依赖

    allowed_list = "\n".join(sorted(ALLOWED_FUNCS))
    system = (
        "你是 capylulu 自动化任务拆解助手，把用户自然语言描述拆成可执行的定时任务。\n"
        "module.func 只能从下列白名单中选择，严禁编造；必须从列表原样复制完整的 module.func 字符串，"
        "不得自行拼接模块名：\n"
        f"{allowed_list}\n"
        "严格输出 JSON（不要多余文字）。两种形态二选一：\n"
        "形态 A（单步）：字段 "
        '{"name": "简短任务名", "cron": "分 时 日 月 周 五段cron", "module": "模块", "func": "函数", '
        '"params": {参数对象}, "note": "一句说明"}。\n'
        "形态 B（多步，用于需要连续操作的完整流程）：字段 "
        '{"name": "简短任务名", "cron": "分 时 日 月 周 五段cron", '
        '"steps": [{"module": "模块", "func": "函数", "params": {参数对象}, "desc": "这一步做什么"}, ...], '
        '"note": "一句说明"}。steps 顺序即执行顺序，每步都只能选白名单函数；'
        "涉及打开应用后用 UI 操作（点击/输入/窗口切换等）配合的完整流程必须用形态 B。\n"
        "拆解铁律：\n"
        "1. “打开/启动某应用（不限定后续操作）”才允许只拆 launch_app；只要描述里包含对应用/网页的后续操作"
        "（发消息、搜索、点击、输入、提交、翻页等），必须拆成完整 steps，例如：\n"
        '   用户说“打开钉钉发消息给罗永，内容为你好”→ steps: '
        '[{"func": "launch_app", "params": {"name": "钉钉"}}, {"func": "window_focus", "params": {"title_substr": "钉钉"}}, '
        '{"func": "ui_click_ref", "params": {"index": 1}} 或 window_inspect 后按编号点击联系人, '
        '{"func": "type_text", "params": {"text": "你好", "enter": true}}] 等，按窗口实际控件编号逐步操作；\n'
        "2. 桌面窗口操作一律用 launch_app / window_focus / window_inspect / ui_click / ui_click_ref / "
        "type_text / key_simulate / mouse_click / mouse_scroll；网页操作一律用 browser_open / browser_goto / "
        "browser_inspect / browser_click_ref / browser_fill / browser_press 等 browser_*；\n"
        "3. 严禁用知识库（kb_*）、便签、文件（append_file 等）、记忆、MCP 等与 UI 无关的函数冒充界面操作；\n"
        "4. 拆出的步骤必须真正完成用户描述的动作；只启动应用而不执行后续操作视为未完成任务，禁止这样输出；\n"
        "5. 拿不准控件编号/步骤细节时，优先拆 window_inspect / browser_inspect 获取快照编号，再按编号操作；"
        "无法拆出可靠完整流程时，输出 {\"ok\": false, \"note\": \"原因\"}。\n"
        "无法用白名单函数完成时，输出 {\"ok\": false, \"note\": \"原因\"}。"
    )
    try:
        llm = create_llm()
        resp = llm.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            tools=None,
        )
        data = _extract_json(resp.get("content") or "")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"LLM 拆解失败：{exc}"}
    if not data:
        return {"ok": False, "error": "LLM 未返回可解析的 JSON"}
    if data.get("ok") is False:
        return {"ok": False, "error": str(data.get("note") or "任务无法拆解为白名单函数")}
    name = str(data.get("name") or "").strip()
    cron = str(data.get("cron") or "").strip()
    if not name or not cron:
        return {"ok": False, "error": "拆解结果缺少 name/cron"}
    steps = data.get("steps")
    if isinstance(steps, list) and steps:
        # 形态 B：多步脚本
        err = _validate_steps(steps)
        if err:
            return {"ok": False, "error": err}
        try:
            parse_cron(cron)
        except ValueError as exc:
            return {"ok": False, "error": f"拆解 cron 非法：{exc}"}
        return {
            "ok": True,
            "name": name,
            "cron": cron,
            "steps": steps,
            "note": str(data.get("note") or "").strip(),
        }
    # 形态 A：单步
    module = str(data.get("module") or "").strip()
    func = str(data.get("func") or "").strip()
    if not module or not func:
        return {"ok": False, "error": "拆解结果缺少 module/func（或 steps 多步脚本）"}
    params = data.get("params") or {}
    if not isinstance(params, dict):
        params = {}
    full = f"{module}.{func}"
    if full not in ALLOWED_FUNCS:
        # 容错：LLM 偶尔会把模块名编错（如 desktop 写成 file_ops），
        # 若函数名在白名单内唯一命中，则自动修正为真实模块路径，避免普通用户反复失败
        cands = [f for f in ALLOWED_FUNCS if f.rsplit(".", 1)[-1] == func]
        if len(cands) == 1:
            full = cands[0]
            module, func = full.rsplit(".", 1)[0], full.rsplit(".", 1)[-1]
        else:
            return {"ok": False, "error": f"拆解结果不在白名单：{full}"}
    try:
        parse_cron(cron)
    except ValueError as exc:
        return {"ok": False, "error": f"拆解 cron 非法：{exc}"}
    return {
        "ok": True,
        "name": name,
        "cron": cron,
        "module": module,
        "func": func,
        "params": params,
        "note": str(data.get("note") or "").strip(),
    }
