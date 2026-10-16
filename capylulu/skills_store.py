"""技能广场存储：<data_dir>/skills.json。

记录已接入的 skill / MCP 入口（名称 / 类型 / 说明 / 来源），供技能广场页展示与增删。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .config import config

STORE = config.data_dir / "skills.json"


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global STORE
    STORE = config.data_dir / "skills.json"

DEFAULT_SKILLS = [
    {
        "name": "文件整理",
        "type": "skill",
        "desc": "按类型/关键字智能整理文件夹，归类到子文件夹",
        "source": "builtin",
        "tool": "skill_organize_files",
        "trigger": "整理,归类,分类,收纳,文件夹太乱",
        "runtime": "builtin",
    },
    {
        "name": "文档语义搜索",
        "type": "skill",
        "desc": "按主题/关键词检索本地文档标题与正文内容",
        "source": "builtin",
        "tool": "skill_doc_search",
        "trigger": "文档,资料,搜索,查找,关键词,主题",
        "runtime": "builtin",
    },
    {
        "name": "图片语义搜索",
        "type": "skill",
        "desc": "按文件名关键词/修改时间搜索图片/照片/截图",
        "source": "builtin",
        "tool": "skill_image_search",
        "trigger": "图片,照片,截图,找图",
        "runtime": "builtin",
    },
    {
        "name": "发票识别",
        "type": "skill",
        "desc": "扫描并列出目录下的发票文件清单（PDF/图片）",
        "source": "builtin",
        "tool": "skill_invoice_scan",
        "trigger": "发票,报销,invoice",
        "runtime": "builtin",
    },
    {
        "name": "图片处理",
        "type": "skill",
        "desc": "图片缩放、裁剪、格式转换（PNG/JPG/WebP）",
        "source": "builtin",
        "tool": "skill_image_edit",
        "trigger": "缩放,裁剪,转换格式,改尺寸,图片处理",
        "runtime": "builtin",
    },
]

# 内置技能 → 可调度工具映射（供「已接入」标识与工具注册校验）
BUILTIN_TOOL_MAP = {x["name"]: x.get("tool", "") for x in DEFAULT_SKILLS}


def _load() -> list[dict]:
    if not STORE.exists():
        return [dict(x) for x in DEFAULT_SKILLS]
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            # 存量数据迁移：内置技能补齐 tool/trigger/runtime 字段
            defaults = {x["name"]: x for x in DEFAULT_SKILLS}
            for x in data:
                d = defaults.get(x.get("name"))
                if d:
                    for k, v in d.items():
                        x.setdefault(k, v)
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return [dict(x) for x in DEFAULT_SKILLS]


def _save(items: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def load_skills() -> list[dict]:
    return _load()


def add_skill(name: str, skill_type: str, desc: str, source: str = "manual") -> str:
    name = (name or "").strip()
    if not name:
        return "名称不能为空"
    items = _load()
    if any(x.get("name") == name for x in items):
        return f"已存在同名技能：{name}"
    items.append({
        "name": name,
        "type": (skill_type or "skill").strip(),
        "desc": (desc or "").strip(),
        "source": source,
        "created": time.strftime("%Y-%m-%d %H:%M"),
    })
    _save(items)
    return ""


def remove_skill(name: str) -> str:
    items = _load()
    for x in items:
        if x.get("name") == name:
            if x.get("source") == "builtin":
                return f"「{name}」是内置技能，不能删除"
            items.remove(x)
            _save(items)
            return ""
    return f"未找到技能：{name}"


def to_rows() -> list[list]:
    """Dataframe 用二维数组：名称 / 类型 / 说明 / 来源。"""
    return [[x.get("name", ""), x.get("type", ""), x.get("desc", ""), x.get("source", "")] for x in _load()]
