"""技能运行时（SKILL.md）：把 <data_dir>/skills/*.md 技能文件解析并交给 LLM 执行。

每个技能是一个 Markdown 文件（参考 CowAgent 的 SKILL.md manifest 风格）：
- front-matter（--- 包裹的 YAML）：name / description / tools / trigger / runtime；
- 正文：面向 LLM 的中文执行指令（步骤、注意、边界），运行时可注入模型上下文，
  并通过 tools 字段限定可调用工具，实现「对话式技能调度」。

典型文件：

    ---
    name: 文件整理
    description: 按类型/关键字智能整理文件夹
    tools:
      - skill_organize_files
    trigger: 整理,归类,分类
    runtime: builtin
    ---
    ## 目标
    按用户指定的目录与模式把散乱文件归类到子文件夹。
    ## 执行步骤
    1. ...
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..config import config

# 注意：tools.registry 在函数内延迟导入（run_skill），
# 避免 skills → tools → skill_md_tools → skills 的循环导入。

# 技能目录（随 config.data_dir 迁移）
SKILLS_DIR = config.data_dir / "skills"

# front-matter 解析：开头 `---` 到下一个 `---` 之间为 YAML，其余为正文
_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)

# 内置技能清单（与 skills_store.DEFAULT_SKILLS 一一对应，用于迁移生成 SKILL.md）
BUILTIN_SKILLS = [
    {
        "name": "文件整理",
        "description": "按类型/关键字智能整理文件夹，归类到子文件夹",
        "tools": ["skill_organize_files"],
        "trigger": "整理,归类,分类,收纳,文件夹太乱",
        "body": (
            "## 目标\n"
            "按用户指定的目录与模式，把该目录第一层散乱文件归类到子文件夹，让目录清爽有序。\n"
            "## 执行步骤\n"
            "1. 确认目录绝对路径存在且是文件夹；\n"
            "2. 确认模式：type=按扩展名分组（图片/视频/音频/文档/压缩包/代码/其他），"
            "keyword=按文件名关键字分组（keywords 逗号分隔，每个关键字建一个文件夹）；\n"
            "3. 调用工具执行归类，只处理第一层文件，不递归不动子目录；\n"
            "4. 向用户汇报移动清单：文件原名 → 目标子文件夹。\n"
            "## 注意\n"
            "- 目录不存在时如实告知；keyword 模式必须提供关键字；"
            "- 不删除任何文件，重名时自动加时间戳后缀保留两副本。"
        ),
    },
    {
        "name": "文档语义搜索",
        "description": "按主题/关键词检索本地文档标题与正文内容",
        "tools": ["skill_doc_search"],
        "trigger": "文档,资料,搜索,查找,关键词,主题",
        "body": (
            "## 目标\n"
            "按用户给出的关键词在指定目录中检索文档，返回匹配文件路径与命中片段。\n"
            "## 执行步骤\n"
            "1. 确认搜索目录绝对路径；\n"
            "2. 确认关键词（必填）；\n"
            "3. 调用工具递归检索：先匹配文件名，再匹配 txt/md/csv/json/yaml 等文本类文件正文；\n"
            "4. 把命中结果整理成清单（路径 + 命中片段）反馈用户，结果过多时截断并说明。\n"
            "## 注意\n"
            "- 关键词缺失时提示用户补充，不要猜测；"
            "- 仅检索本地文件，不联网、不修改任何文件。"
        ),
    },
    {
        "name": "图片语义搜索",
        "description": "按文件名关键词/修改时间搜索图片/照片/截图",
        "tools": ["skill_image_search"],
        "trigger": "图片,照片,截图,找图",
        "body": (
            "## 目标\n"
            "在指定目录中按文件名关键词或修改时间查找图片（jpg/png/gif/webp 等）。\n"
            "## 执行步骤\n"
            "1. 确认搜索目录绝对路径；\n"
            "2. 确认关键词（可省略）与时间范围（days>0 表示只看最近 N 天，0/省略不限）；\n"
            "3. 调用工具递归搜索并返回匹配图片路径列表；\n"
            "4. 把图片路径整理成清单反馈用户。\n"
            "## 注意\n"
            "- 不做图片内容识别，只按文件名/时间匹配；"
            "- 结果过多时截断并说明，不修改任何文件。"
        ),
    },
    {
        "name": "发票识别",
        "description": "扫描并列出目录下的发票文件清单（PDF/图片）",
        "tools": ["skill_invoice_scan"],
        "trigger": "发票,报销,invoice",
        "body": (
            "## 目标\n"
            "扫描指定目录，找出发票文件（文件名含 发票/invoice/票 的 pdf/png/jpg），返回清单。\n"
            "## 执行步骤\n"
            "1. 确认扫描目录绝对路径；\n"
            "2. 调用工具递归扫描并收集发票文件路径、大小、修改时间；\n"
            "3. 把清单（路径/大小/修改时间）整理反馈用户；\n"
            "4. 若用户需要票面金额等结构化信息，提示需要多模态识别能力并说明现状。\n"
            "## 注意\n"
            "- 仅做文件级扫描识别，不改动、不移动任何发票文件。"
        ),
    },
    {
        "name": "图片处理",
        "description": "图片缩放、裁剪、格式转换（PNG/JPG/WebP）",
        "tools": ["skill_image_edit"],
        "trigger": "缩放,裁剪,转换格式,改尺寸,图片处理",
        "body": (
            "## 目标\n"
            "对单张图片执行缩放 / 裁剪 / 格式转换，输出到原目录（_edited 后缀，不覆盖原图）。\n"
            "## 执行步骤\n"
            "1. 确认图片文件绝对路径存在；\n"
            "2. 确认操作类型：scale（缩放比例 0.1~5）/ crop（box=left,top,right,bottom）/ "
            "convert（to_format=png/jpg/webp）；\n"
            "3. 调用工具处理并得到输出路径；\n"
            "4. 汇报输出文件路径与原图未变。\n"
            "## 注意\n"
            "- 参数缺失或非法时先向用户澄清，不擅自猜测；"
            "- 原图始终保留，处理失败时如实报告原因。"
        ),
    },
]

# 按名称索引内置技能（生成 SKILL.md 时复用）
BUILTIN_BY_NAME = {x["name"]: x for x in BUILTIN_SKILLS}


@dataclass
class Skill:
    """一个已解析的 SKILL.md 技能。"""
    name: str
    description: str = ""
    tools: list[str] = field(default_factory=list)
    trigger: str = ""
    runtime: str = "custom"
    body: str = ""
    path: str = ""


def build_skill_md(name: str, description: str, tools: list[str] | None = None,
                   trigger: str = "", steps: str = "", runtime: str = "custom") -> str:
    """按 SKILL.md manifest 风格拼装技能 Markdown 文本。

    steps 非空时写入「执行步骤」小节；为空则写一个通用占位小节，方便用户后续补充。
    """
    name = (name or "").strip()
    tools = [t for t in (tools or []) if str(t).strip()]
    tools_yaml = "".join(f"      - {t}\n" for t in tools) or "      []\n"
    body = (steps or "").strip()
    if body:
        # 用户可能直接粘贴步骤文本，统一包进「执行步骤」小节
        if not body.startswith("##"):
            body = "## 执行步骤\n" + body
        # 正文自带「## 目标」时直接复用；否则前置目标小节，避免重复
        if not body.startswith("## 目标"):
            body = "## 目标\n" + description + "\n\n" + body
    else:
        body = (
            "## 目标\n" + description + "\n\n"
            "## 执行步骤\n"
            "1. 理解用户任务与技能目标；\n"
            "2. 按需调用下方 tools 字段列出的工具完成操作；\n"
            "3. 整理结果并汇报给用户。"
        )
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "tools:\n" + tools_yaml +
        (f"trigger: {trigger}\n" if trigger else "") +
        f"runtime: {runtime}\n"
        "---\n\n"
        f"{body}\n"
    )


def parse_skill_md(path: str | Path) -> Skill:
    """解析单个 SKILL.md 文件 → Skill 对象；格式非法时抛 ValueError。"""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        raise ValueError(f"SKILL.md 缺少 front-matter（--- 包裹的 YAML）：{p}")
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"SKILL.md front-matter 解析失败：{p} ({exc})") from exc
    if not isinstance(meta, dict):
        raise ValueError(f"SKILL.md front-matter 必须是映射：{p}")

    tools = meta.get("tools") or []
    if isinstance(tools, str):
        tools = [x.strip() for x in tools.split(",") if x.strip()]
    elif not isinstance(tools, list):
        tools = []

    name = str(meta.get("name") or p.stem).strip()
    return Skill(
        name=name,
        description=str(meta.get("description") or "").strip(),
        tools=[str(t).strip() for t in tools if str(t).strip()],
        trigger=str(meta.get("trigger") or "").strip(),
        runtime=str(meta.get("runtime") or "custom").strip(),
        body=(m.group(2) or "").strip(),
        path=str(p),
    )


def list_skills() -> list[dict]:
    """列出技能目录下所有可解析的 SKILL.md（含详情字段）。"""
    items: list[dict] = []
    if not SKILLS_DIR.is_dir():
        return items
    for p in sorted(SKILLS_DIR.glob("*.md")):
        try:
            s = parse_skill_md(p)
        except ValueError:
            continue  # 跳过损坏文件，不阻断整体列表
        items.append({
            "name": s.name,
            "description": s.description,
            "tools": s.tools,
            "trigger": s.trigger,
            "runtime": s.runtime,
            "path": s.path,
            "content": p.read_text(encoding="utf-8"),
        })
    return items


def get_skill(name: str) -> Skill | None:
    """按技能名（或文件名）查找 SKILL.md；找不到返回 None。"""
    name = (name or "").strip()
    if not SKILLS_DIR.is_dir():
        return None
    for p in SKILLS_DIR.glob("*.md"):
        try:
            s = parse_skill_md(p)
        except ValueError:
            continue
        if s.name == name or p.stem == name:
            return s
    return None


def save_skill_md(name: str, md: str) -> Path:
    """把 SKILL.md 文本写入 <data_dir>/skills/<name>.md（目录自动创建）。"""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    p = SKILLS_DIR / f"{name}.md"
    p.write_text(md, encoding="utf-8")
    return p


def ensure_builtin_skills() -> list[str]:
    """把 5 个内置技能各生成一份 SKILL.md 到技能目录（已存在则跳过，幂等）。

    返回本次实际写入的文件路径列表。
    """
    if not SKILLS_DIR.is_dir():
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for item in BUILTIN_SKILLS:
        p = SKILLS_DIR / f"{item['name']}.md"
        if p.exists():
            continue
        md = build_skill_md(
            name=item["name"],
            description=item["description"],
            tools=item["tools"],
            trigger=item["trigger"],
            steps=item["body"],
            runtime="builtin",
        )
        p.write_text(md, encoding="utf-8")
        written.append(str(p))
    return written


def run_skill(name: str, task: str, llm=None, max_iterations: int = 8) -> str:
    """执行技能：把 SKILL.md 正文作为系统指令注入 LLM，按 tools 限定工具做工具循环。

    llm 不传时用 capylulu.llm.create_llm() 创建；无工具或 LLM 调用失败时返回错误信息。
    """
    skill = get_skill(name)
    if skill is None:
        return f"未找到技能 SKILL.md：{name}"
    if llm is None:
        from ..llm import create_llm
        llm = create_llm()

    tools = [t for t in skill.tools if t]
    system = (
        f"你是技能「{skill.name}」的执行者。\n"
        f"技能说明：{skill.description}\n"
        "以下是该技能的 SKILL.md 执行指令，请严格按指令完成用户任务：\n"
        f"{skill.body}\n"
    )
    if tools:
        system += f"\n任务中可使用工具（仅限这些）：{', '.join(tools)}"
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": (task or "").strip() or "请执行该技能"},
    ]

    schemas = None
    if tools:
        from ..tools.registry import get_tool_schemas  # 延迟导入避免循环
        schemas = get_tool_schemas(tools)
    for _ in range(max_iterations):
        try:
            resp = llm.chat(messages, tools=schemas)
        except Exception as exc:  # noqa: BLE001
            return f"技能执行失败（LLM 调用异常）：{exc}"
        content = resp.get("content")
        tool_calls = resp.get("tool_calls")
        if not tool_calls:
            return content or "(技能执行完毕，未返回内容)"

        assistant_msg = {"role": "assistant", "content": content or ""}
        assistant_msg["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                },
            }
            for tc in tool_calls
        ]
        messages.append(assistant_msg)
        for tc in tool_calls:
            name_ = tc["function"]["name"]
            if tools and name_ not in tools:
                result = f"工具 {name_} 不在本技能允许列表 {tools} 中，禁止调用"
            else:
                from ..tools.registry import call_tool  # 延迟导入避免循环
                raw = tc["function"].get("arguments")
                try:
                    args = json.loads(raw) if isinstance(raw, str) and raw else {}
                except (json.JSONDecodeError, TypeError):
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                result = call_tool(name_, args)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})

    return "(技能执行超过最大循环次数，已停止)"
