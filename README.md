# Capylulu · 噜噜

**多管家协作的桌面 AI 助手，佛系淡定帮你操作电脑。**

Capylulu（噜噜）是一个基于 Python 的桌面 AI 助手。以 **Leader 主理人 + 管家 Agent 团队**的模式运行：主理人理解你的意图，分派给对应管家执行——文件管家管文件、电脑管家查系统、浏览器专员上网抓内容。对话、记忆、定时任务、桌宠、七套配色切换，一条 `python run.py` 全搞定。

对标 CowAgent 逐批落地内核九批能力：规划引擎、技能运行时、MCP 生态、三级记忆、知识库、管家团队、自主进化、桌面操作工具、IM 通道。前端为 Vue 3 工作台，以「噜噜黄 · 琥珀暖暗」佛系风格呈现，署名「不许人间见白头」。

---

## 设计哲学

**LLM 决定"做什么"，管家团队决定"谁来做"，工具决定"怎么做"。**

| 层级 | 组成 | 类比 |
| :--- | :--- | :--- |
| `capylulu/agent/` | Leader 主理人 + 管家 Agent（意图路由、规划、循环执行） | **店长 + 店员** |
| `capylulu/tools/` | 工具注册表 + 安全分级（文件 / 系统 / 桌面 / 键鼠） | **工具箱** |
| `capylulu/server_api/` | FastAPI 薄层，暴露 REST API | **柜台** |
| `web/` | Vue 3 前端（导航轨 + 平台状态面板 + 内容区） | **门面** |

能力分层一句话：`agent/` 决定**做什么**与**谁来做**，`skills/` `mcp/` `tools/` 决定**怎么做**，`memory3/` `kb/` `team/` `evolve/` `im/` 提供记忆、知识与协作底座，`server_api/` + `web/` 负责**对外呈现**。

---

## 技术栈

| 分类 | 技术 | 用途 |
|------|------|------|
| 语言 | Python 3.11+ | 主开发语言 |
| 后端 | FastAPI + Uvicorn | REST API + 前端产物托管（端口 6661） |
| 前端 | Vue 3 + Vite + Vue Router | 工作台 UI |
| LLM | 智谱 GLM-4-Flash（默认）/ DeepSeek | 对话与 Agent 推理 |
| 桌宠 | Tkinter + Pillow | 透明置顶水豚（capy） |
| 存储 | JSON + Markdown（data/） | 会话 / 记忆 / 任务 / 台账 / 知识库 |

---

## 九批内核能力总览

对标 CowAgent 逐批落地的内核能力，全部集成在 `capylulu/` 各包中：

| 批次 | 能力 | 核心模块 | 落盘 |
| :--- | :--- | :--- | :--- |
| 1 | **规划引擎 / 能力路由** | `agent/planner.py`（三模式决策：chat / direct / plan；步骤依赖、失败重试与降级）· `agent/leader.py`（能力路由 + 失败自动升级） | `data/plans.json` |
| 2 | **技能运行时（SKILL.md）** | `skills/runtime.py`（解析 / 列表 / 执行技能文件）· 5 个内置技能自动生成 | `data/skills/*.md` |
| 3 | **MCP 生态** | `mcp/store.py` + `client.py` + `market.py` + `dynamic_registry.py`（接入 / 市场一键安装 / 工具动态注册 `mcp_*`） | `data/mcp.json` |
| 4 | **三级记忆与深度蒸馏** | `memory3/store.py` + `dream.py` + `query.py`（工作 / 情景 / 语义记忆，Deep Dream 蒸馏，合并检索） | `data/memory/` |
| 5 | **知识库** | `kb/store.py` + `index.py` + `ask.py`（建库 / 导入切块 / TF-IDF 检索 / LLM 问答） | `data/kb/` |
| 6 | **管家团队** | `team/store.py`（任务台账）+ `agent/`（能力路由、委派、失败自动升级） | `data/team_tasks.json` |
| 7 | **自主进化** | `evolve/lessons.py` + `reflect.py` + `improve.py` + `maybe.py`（经验库 → 反思 → 自我改进飞轮） | `data/evolve/` |
| 8 | **桌面操作工具** | `tools/window_ops.py` / `process_ops.py` / `media_ops.py` / `input_ops.py`（窗口 / 进程 / 媒体 / 键鼠，13 个工具） | `data/screenshots/` |
| 9 | **IM 通道** | `im/channel.py` + `webhook.py` + `httpin.py` + `broker.py`（Webhook / 本地接收 / 消息中心） | `data/im.json` |

> 说明：1 批次为规划路由（PlannerEngine + 能力路由），2~3 批次为执行能力（技能 / MCP），4~5 批次为记忆与知识底座，6~7 批次为团队与进化，8~9 批次为桌面与 IM 入口。各能力详细说明见下文对应章节。

---

## 前端页面说明

前端为 Vue 3 + Vite 单页应用，`web/src/views/` 下 12 个视图文件，导航轨挂载 10 个页面：

| 路由 | 视图文件 | 页面说明 |
|------|----------|----------|
| `/chat` | ChatView.vue | 对话：会话列表 + 噜噜对话（默认页） |
| `/team` | TeamView.vue | 管家团队：成员卡片（图标 + 职责 + 能力标签 + 工具 + 状态）+ 任务台账 |
| `/abilities` | AbilitiesView.vue | 技能能力：技能广场 + 能力中心（SKILL.md 技能 / MCP 服务与市场 / 动态注册工具） |
| `/skills`、`/mcp` | — | 路由重定向至 `/abilities`（旧 SkillsView.vue / McpView.vue 文件保留未挂载） |
| `/tasks` | TasksView.vue | 自动任务：自然语言定时任务 + 执行日志 |
| `/memory` | MemoryView.vue | 用户记忆：单层记忆 + 三级记忆（工作 / 情景 / 语义）+ 深度蒸馏 |
| `/kb` | KbView.vue | 知识库：建库 / 上传文档 / 检索 / LLM 问答 |
| `/evolve` | EvolveView.vue | 自主进化：经验库 + 进化日志 + 反思 / 改进触发 |
| `/im` | ImView.vue | IM 通道：通道配置 + 发送测试 + 模拟推送 + 收件箱 |
| `/tools` | ToolsView.vue | 工具记录：工具调用日志 |
| `/settings` | SettingsView.vue | 模型设置：LLM 配置 + 七套配色切换 |

- 布局：`layout/AppShell.vue` 三栏骨架（左导航轨 / 中平台状态面板 / 右内容区），导航图标统一使用 `web/public/capy/` 水豚素材；
- 风格：噜噜黄 · 琥珀暖暗主色，玻璃卡片风格（`styles/theme.css` 主题变量，7 套配色可切换），署名「不许人间见白头」；
- 素材：`web/public/capy/` 15 张水豚素材——静态 `capy01.png ~ capy08.png`，动图 `capy_gif01.gif ~ capy_gif07.gif`；`web/public/lulu/` 保留旧噜噜形象（桌宠 / 部分图标沿用）；
- 组件：`components/AgentCard.vue`（管家卡片）、`api/index.js`（REST API 封装）、`router/index.js`（路由 + 页面图标）。

---

## 🚀 快速开始

### 1. 环境准备
Windows 10/11，Python 3.11+，Node.js 18+（前端构建用）。

### 2. 安装依赖

```bash
git clone <your-repo>/capylulu.git
cd capylulu
pip install -r requirements.txt
```

按需安装可选依赖：`pip install mcp pypdf`（MCP 客户端 / PDF 文档导入）。

### 3. 配置

复制配置模板并填写 API Key：

```bash
copy config.example.yaml config.yaml
```

编辑 `config.yaml`，填入 LLM API Key（智谱或 DeepSeek 二选一）：

```yaml
llm:
  provider: zhipu        # 或 deepseek
  zhipu:
    api_key: sk-xxx
    base_url: https://open.bigmodel.cn/api/paas/v4/
    model: glm-4-flash
```

> 注意：`config.yaml` 已被 `.gitignore` 排除，**严禁提交真实 Key 到仓库**；模板 `config.example.yaml` 可正常提交。

### 4. 启动

```bash
python run.py
```

访问 `http://127.0.0.1:6661`，用噜噜的语气跟它说话即可。

### 开发模式（前后端分离热更新）

```bash
# 终端 1：后端 API
python -m uvicorn capylulu.server_api.main:app --host 0.0.0.0 --port 6661

# 终端 2：前端热更新
cd web && npm install && npm run dev        # http://localhost:5173
```

> `run.py` 托管的是 `web/dist` 产物。改完前端源码需 `npm run build` 后重启或强刷（Ctrl+F5），否则页面不会更新。

---

## 目录结构

```
capylulu/
│
├── run.py                  一键启动入口（uvicorn :6661 + Vue dist 托管）
├── requirements.txt        后端依赖（openai / pyyaml）
├── config.example.yaml     配置模板（可提交仓库）
├── config.yaml             LLM、Agent、配色等配置（含真实 Key，.gitignore 排除）
├── .gitignore              已就绪：排除 config.yaml / data / node_modules 等
├── README.md               本文档
│
├── capylulu/               ── 核心包 ──
│   ├── agent/              Leader 主理人 + 管家 Agent
│   │   ├── leader.py       主理人：意图理解、能力路由、失败自动升级
│   │   ├── planner.py      规划引擎（PlannerEngine：chat / direct / plan 三模式决策）
│   │   ├── router.py       管家路由（能力 + 名称匹配）
│   │   ├── loop.py         Agent 工具循环
│   │   ├── workers.py      管家执行器
│   │   ├── base.py         基类与通用逻辑
│   │   └── prompts.py      提示词（LEADER_PLANNER_PROMPT 等）
│   ├── llm/                LLM 客户端（base / client，智谱 / DeepSeek）
│   ├── skills/             SKILL.md 技能运行时（runtime.py）
│   ├── mcp/                MCP 生态（store / client / market / dynamic_registry）
│   ├── memory3/            三级记忆（store / dream 蒸馏 / query 合并检索）
│   ├── kb/                 知识库（store / index / ask）
│   ├── team/               管家团队任务台账（store）
│   ├── evolve/             自主进化（lessons / reflect / improve / maybe）
│   ├── im/                 IM 通道（channel / webhook / httpin / broker）
│   ├── tools/              工具注册表 + 安全分级（registry + 文件/系统/桌面/键鼠/技能/记忆/知识库/MCP 工具）
│   ├── server_api/         FastAPI 层（main.py + routers/ 12 个板块）
│   │   └── routers/        chat / team / skills / tasks / memory / kb / evolve / im / tools / settings / mcp / misc
│   ├── ui/                 配色主题（PALETTES 7 套）、公共函数
│   ├── agents_store.py     管家团队持久化（agents.json）
│   ├── skills_store.py     技能管理
│   ├── plans_store.py      规划日志（plans.json）
│   ├── scheduler.py        定时任务调度
│   ├── memory.py           用户记忆（Markdown）
│   ├── history.py          会话历史
│   ├── tool_log.py         工具调用日志
│   ├── pet.py              桌宠（Tkinter 置顶透明）
│   └── config.py           配置加载
│
├── web/                    ── 前端（Vite + Vue 3）──
│   ├── package.json        capylulu-web v2.0.0（dev / build / preview）
│   ├── src/
│   │   ├── layout/AppShell.vue   三栏骨架（导航轨 + 状态面板 + 内容区）
│   │   ├── components/AgentCard.vue  管家卡片组件
│   │   ├── composables/toast.js      轻提示
│   │   ├── views/                12 个视图：Chat / Team / Abilities / Tasks / Memory / Kb / Evolve / Im / Tools / Settings（+ 保留未挂载的 Skills / Mcp）
│   │   ├── router/index.js       路由（/skills、/mcp 重定向至 /abilities）
│   │   ├── styles/theme.css      配色变量（7 套）
│   │   └── api/index.js          REST API 封装
│   ├── public/
│   │   ├── capy/                 水豚素材 15 张：capy01~08.png + capy_gif01~07.gif
│   │   └── lulu/                 噜噜形象图（1~7.png，桌宠等沿用）
│   └── dist/                    npm run build 产物（run.py 托管，.gitignore 排除）
│
└── data/                    ── 运行时数据（.gitignore 排除，不入库）──
    ├── sessions.json            对话会话
    ├── agents.json              管家团队
    ├── skills.json              技能
    ├── plans.json               规划日志（决策 JSON / 步骤 / 耗时 / 结果）
    ├── mcp.json                 MCP 接入服务（含 tools_cache 工具缓存）
    ├── tasks.json               定时任务
    ├── task_logs.json           任务执行日志
    ├── tool_logs.json           工具调用日志
    ├── team_tasks.json          管家团队任务台账
    ├── im.json                  IM 通道配置
    ├── memory/                  记忆（working / episodic / semantic 三级 + *.md）
    ├── notes/                   便签
    ├── screenshots/             截图
    ├── skills/                  技能文件（SKILL.md）
    ├── kb/                      知识库（每库一目录）
    ├── evolve/                  进化（lessons / evolution_log / .last_evolve.json）
    └── im/                      收件箱（inbox.json）
```

---

## 上传 Gitee 说明

项目已为公开上传做好准备，遵循以下约定：

1. **`.gitignore` 已就绪**，已排除：`config.yaml`（真实 Key）、`*.local.yaml`、`.env`、`data/`（全部运行时数据）、`node_modules/`、`web/dist`、`__pycache__/`、`.ohmyagent/`、`.vscode/`、日志等；
2. **严禁提交 `config.yaml` 真实 Key**：仓库只提交 `config.example.yaml` 模板（Key 留空），使用者自行 `copy config.example.yaml config.yaml` 填写；
3. **`data/` 运行时数据不入库**：会话、台账、日志、截图、本地记忆与知识库均为个人运行时产物，由 `.gitignore` 整体排除；
4. 推送前建议自检：`git status` 确认无 `config.yaml` / `data/` 被暂存，`git check-ignore config.yaml data/` 应返回命中；
5. 提交命令示例：

```bash
git add .
git commit -m "capylulu: 九项内核能力落地，更新 README"
git remote add origin https://gitee.com/<your-account>/capylulu.git
git push -u origin master
```

---

## 一次对话是怎么跑的

```
你在对话框里说"帮我找桌面的发票"
    ↓
ChatView.vue                POST /api/chat/send
    ↓
routers/chat.py             组装历史消息，交给 Agent
    ↓
agent/leader.py             主理人判断意图 → 路由到「文件管家」（能力路由优先）
    ↓
agent/planner.py            （复杂任务）规划引擎决策：chat / direct / plan
    ↓
agent/loop.py               管家循环：调用工具 → 看结果 → 继续或收尾
    ↓
tools/file_ops.py           文件管家调 search_files / list_dir 找到发票
    ↓
响应回流前端                噜噜语气 + 结果展示
```

关键契约（`capylulu/agent/`）：

- 统一入口：`agent.run(user_input, chat_history, specialist='自动')`
- `chat_history` 传入**不含当前消息**的历史列表（prev），内部先 normalize 再拼接
- 模型是否就绪用 `ui.common._llm_ready()` 判断；离线时不调用模型，给佛系提示文案
- 改模型 / 管家后用 `agent.reconfigure()` 重载

---

## 管家团队

主理人（Leader）+ 若干管家（Worker），内置管家：

| 管家 | 职责 | 主要工具 |
|------|------|----------|
| 文件管家 | 读、写、搜、整理文件 | read_file / write_file / append_file / list_dir / search_files / move_file |
| 电脑管家 | 系统信息、磁盘、时间、设置 | system_info / disk_usage / now_datetime / open_settings |
| 浏览器专员 | 打开网页、抓取摘要 | open_url / fetch_page |

- 持久化在 `data/agents.json`，Web「管家团队」页可增删改、启停
- 内置管家不可删除、不可改名，但可停用、可编辑 prompt/role
- 自定义管家：给个名字 + role + 关键词 + 工具列表即可，改完 `agent.reconfigure()` 生效
- 批次6 升级：Agent 元数据（`capabilities` / `description` / `icon`）扩展、能力路由优先、委派失败自动升级（重试 → 按能力转交 → Leader 全量工具兜底 → `escalated` / `failed` 状态），委派全程写入 `data/team_tasks.json` 任务台账，Web「管家团队」页可查看统计与手动委派测试

---

## 自主进化（批次7）

对标 CowAgent 的 Agent 自主进化能力，构建「感知 → 沉淀 → 应用」闭环：从任务台账反思提炼经验，再基于经验自动改进自身，形成自我进化飞轮。

- **经验库**（`capylulu/evolve/lessons.py`）：落盘 `data/evolve/lessons.json`，条目含 `trigger` / `advice` / `task_ref` / `confidence` / `applied` / `created_at`；支持增删查、应用计数，`trigger + advice` 相同自动去重；
- **反思引擎**（`reflect.py`）：从任务台账最近已完成 / 失败任务批量反思——LLM 提炼成功经验与失败教训写经验库；LLM 不可用规则降级；新经验同步写入 memory3 情景记忆；
- **自我改进**（`improve.py`）：基于经验库生成改进建议，LLM 评估 `apply / target / patch_text / risk`——**低风险**自动应用（追加 Agent prompt 注意项或注入总代理偏好，`agent.reconfigure()` 即时生效）；**高风险**仅记录待人工确认；自动应用上限 `max_auto`（默认 3）条防失控；
- **自动触发**（`maybe.py`）：`maybe_evolve(interval_seconds, min_new_tasks)` 按间隔（默认 3600s）或新增任务数触发，时间戳记录 `data/evolve/.last_evolve.json`；
- **前端**：`EvolveView.vue`（经验库列表与手动新增、进化日志、触发反思 / 改进按钮、状态条）。

---

## 规划引擎（Planner Engine）

复杂任务交给独立规划引擎 `capylulu/agent/planner.py`（PlannerEngine）决策与编排：

- **三模式决策**：LLM 输出 JSON 选择 `chat`（纯聊天）/ `direct`（单执行者）/ `plan`（多步骤协作），Leader 的 `run_orchestrated` 只做门面转发；
- **步骤依赖**：plan 的每个 step 可声明 `depends`（前置步骤序号），依赖未成功自动跳过并标注「依赖未满足」；
- **失败重试与降级**：单步失败自动重试 1 次；全部失败降级为 Leader 全量工具直接处理；
- **资源感知**：决策提示自动列出技能库内置技能与已启用 MCP 服务，`direct`/`plan` 的 agent 可为「技能库 / MCP」等虚拟资源名；
- **过程可观测**：决策 JSON、步骤数、耗时、执行结果写入 `data/plans.json`（`capylulu/plans_store.py`）。

调用链：`server_api/routers/chat.py → agent.run → leader.run_orchestrated → planner.run`。

---

## 技能运行时（SKILL.md）

技能是真正可解析、可执行的「技能文件」，参考 CowAgent 的 SKILL.md manifest 风格：

- **目录结构**：`data/skills/<技能名>.md`，YAML front-matter（`name` / `description` / `tools` / `trigger` / `runtime`）+ 中文执行指令正文；
- **运行时**：`capylulu/skills/runtime.py` 提供 `parse_skill_md` / `list_skills` / `get_skill` / `run_skill`（注入正文 + 按 `tools` 限定工具循环）；
- **内置迁移**：5 个内置技能（文件整理 / 文档语义搜索 / 图片语义搜索 / 发票识别 / 图片处理）启动时自动生成，幂等；
- **对话式创建**：工具 `skill_create` / `skill_detail` / `skill_list_files`；REST `GET /api/skills/files`、`POST /api/skills/create`；
- **前端**：`AbilitiesView.vue` 技能广场区（清单 / 详情 / 创建表单）。

---

## MCP 生态

`capylulu/mcp/` 提供 CowAgent 式 MCP（Model Context Protocol）接入能力：

- **接入与存储**：`store.py` 管理 `data/mcp.json`（CRUD、启停、`tools_cache`），支持 `stdio` / `sse` / `http`；
- **客户端**：`client.py` 基于官方 `mcp` SDK，SDK 缺失时优雅降级；
- **MCP 市场**：`market.py` 内置常见服务目录（filesystem / fetch / memory / sequential-thinking / time / git / sqlite / everart / github / weather 等），关键字搜索 + 一键安装（写入 → 真实连接刷新缓存 → 动态注册）；
- **工具动态注册**：`dynamic_registry.py` 把启用 server 的工具注册进主工具表，命名 `mcp_<server>_<tool>`，调用自动转发 `client.py`；
- **前端**：`AbilitiesView.vue` 能力中心（服务管理 + MCP 市场 + 动态注册工具面板）。

---

## 工具与安全分级

`capylulu/tools/registry.py` 统一注册，三级风险：

| 级别 | 行为 |
|------|------|
| low | 自动执行 |
| medium | 记录日志 |
| high | 禁止自动执行（需用户确认通道） |

新增工具：在 `tools/` 下写函数 → `@register` 装饰（name / description / parameters / risk）→ 重启生效。Web「工具记录」页查看调用日志（`data/tool_logs.json`）。

---

## 桌面操作工具

对标 CowAgent 桌面能力的 Windows 桌面操作工具集，共 13 个工具，分布在 `tools/` 四个模块：

### 窗口管理 `tools/window_ops.py`（ctypes/user32）

| 工具 | 功能 | 风险 |
|------|------|------|
| `window_list` | 列出可见窗口：标题 / 进程名 / PID / 句柄，支持关键字过滤 | low |
| `window_activate` | 按标题关键字激活置前（自动还原最小化） | medium |
| `window_minimize` / `window_maximize` / `window_restore` | 最小化 / 最大化 / 还原窗口 | medium |
| `window_close` | 向窗口发送 WM_CLOSE 关闭请求（可能触发未保存提示） | high |

### 进程管理 `tools/process_ops.py`（PowerShell）

| 工具 | 功能 | 风险 |
|------|------|------|
| `process_list` | 列出进程：进程名 / PID / 内存 / 主窗口标题，支持关键字过滤 | low |
| `process_kill` | 结束进程（按 PID 或进程名），**系统关键进程白名单保护**（explorer / svchost / lsass / dwm 等，PID < 100 一律拒绝） | high |

### 媒体控制 `tools/media_ops.py`（winmm + WMI）

| 工具 | 功能 | 风险 |
|------|------|------|
| `volume_get` | 读取当前系统音量（0-100） | low |
| `volume_set` | 设置系统音量（waveOut 主输出通道） | medium |
| `brightness_set` | 设置显示器亮度（WMI WmiMonitorBrightness），显示器不支持时返回说明 | medium |

### 屏幕与键鼠 `tools/input_ops.py`（PowerShell + keybd_event）

| 工具 | 功能 | 风险 |
|------|------|------|
| `screenshot` | 截取全屏（多显示器虚拟桌面）或活动窗口，保存到 `data/screenshots/` 并返回路径 | medium |
| `key_simulate` | 模拟安全按键组合，**仅白名单**：`win+d/e/l`、`ctrl+c/v/x/a/z/y`、`alt+tab`、`alt+f4`、`enter`、`esc`、`f5` | high |

> 说明：`high` 风险工具（关窗 / 杀进程 / 按键模拟）在 `registry.call_tool` 层禁止自动执行，需用户确认后经确认通道调用。

---

## IM 通道（批次9）

对标 CowAgent 的 IM 消息接入：把外部 IM 平台消息接进 capylulu，由 Leader 处理并把回复经原通道发回。

- **模块**：`capylulu/im/`（`channel.py` 通道抽象 + 注册表 · `webhook.py` 机器人 Webhook 通道 · `httpin.py` 本地接收通道 · `broker.py` 消息中心）；
- **通道抽象**：`IMChannel` 基类（`send(text)` / `poll()` / `close()` / `from_config()` / `to_dict()`），`register_channel_type()` 注册新类型；**新增通道只需实现子类并注册**；
- **Webhook 通道**：钉钉 / 企业微信群机器人标准 Webhook，POST `{"msgtype": "text", "text": {"content": text}}`，解析 `errcode` 返回成功 / 失败；
- **本地接收通道**：模拟 IM 服务器推送——外部 POST `/api/im/inbox/incoming` 写入收件箱，方便无真实机器人时联调；
- **消息中心**：通道配置存 `data/im.json`，收件箱存 `data/im/inbox.json`；`enqueue()` 入队 → `process_pending()` 交给 Leader → 回复经原通道 `send()` 回发 → 标记 processed / failed；轮询用 `poll_channels()`，不引入调度框架；
- **前端**：`ImView.vue`（通道配置表单 + 发送测试 + 模拟推送 + 收件箱列表与回复状态）。

> ⚠️ **协议风险说明**：本项目**只实现标准 Webhook（钉钉 / 企业微信群机器人）与本地接收通道**，**不实现**任何微信 / QQ 个人号接入（扫码登录、逆向协议、Hook 客户端等）。个人号通道违反 IM 平台服务条款、存在封号风险且协议不稳定，明确不提供；若需微信 / QQ 场景，建议走官方机器人 / 企业微信应用消息 / 第三方合规网关，并通过 `register_channel_type()` 扩展自定义通道。

---

## 三级记忆与深度蒸馏

对标 CowAgent 的三级记忆架构，在单层记忆（`data/memory/*.md`）之上新增三个子目录（互不干扰、可同时使用）：

| 层级 | 目录 | 内容 | 字段 |
|------|------|------|------|
| 工作记忆 | `data/memory/working/` | 会话级上下文，同会话自动合并追加 | session / content / updated_at |
| 情景记忆 | `data/memory/episodic/` | 结构化事件记录，可批量蒸馏 | time / task / action / result / agents |
| 语义记忆 | `data/memory/semantic/` | 蒸馏后的长期知识，同主题合并 | topic / points / sources / confidence / updated_at |

- **模块**：`capylulu/memory3/`（`store.py` 三级存储 CRUD · `dream.py` 蒸馏引擎 · `query.py` 合并检索），数据目录迁移后调用 `refresh_paths()` 对齐路径；
- **Deep Dream 蒸馏**：情景记忆批量总结生成/合并语义记忆——LLM 可用走 LLM 总结；不可用**规则降级**（关键词频次 + 高频主题聚类）。支持手动触发（`deep_dream()` / Web「深度蒸馏」按钮 / 工具 `memory_deep_dream`）与按间隔自动触发（`maybe_auto_dream`，时间戳 `data/memory/.last_dream.json`）；
- **合并检索**：`query(keyword, limit)` 按**语义 > 情景 > 工作**基础优先级 × 时间衰减（半衰期：语义 365 天 / 情景 30 天 / 工作 1 天）合并排序；`memory_brief()` 输出简报供 Leader 决策注入；
- **前端**：`MemoryView.vue`（工作 / 情景 / 语义分区 + 合并检索 + 蒸馏状态与按钮）。

---

## 知识库

对标 CowAgent 的本地知识库：`data/kb/<库名>/` 每库一个目录，文档导入即切块建索引，支持关键词检索与 LLM 问答。

- **模块**：`capylulu/kb/`（`store.py` 库与文档管理 · `index.py` 索引与检索 · `ask.py` 问答）；
- **文档导入**：txt / md / csv / json / yml / log / py 等文本类直接入库；pdf 装有 pypdf 时自动解析；导入按 500 字窗口、50 字重叠切块，写库内 `index.json`；
- **索引检索**：中文 2~4 字窗口粗分词 + TF-IDF 风格倒排评分，`search(kb, query, top_k)` 返回 top-k 文档块并带来源引用；kb 留空即跨库检索；
- **问答**：检索 top-k 块 + LLM 生成回答（要求基于片段、标注 [来源 N]）；LLM 不可用降级返回相关片段与来源；
- **前端**：`KbView.vue`（建库、上传文档、库内文件列表、关键词搜索、LLM 问答）。

---

## 记忆与便签

- **记忆**：`data/memory/*.md`，噜噜据此记住你的偏好与知识，Web「用户记忆」页可增删改
- **便签**：`data/notes/*.md`，说"记个便签"即生成
- **会话**：`data/sessions.json`，对话历史可重命名、删除

---

## 定时任务

`data/tasks.json` + `scheduler.py`，Web「自动任务」页管理：

- 自然语言描述任务（如"每天 18:40 提醒我下班"）
- 可启停、删除，查看执行日志（`data/task_logs.json`）

---

## 桌宠

启动后点「召唤桌宠」拉起 `capylulu/pet.py`：

- Tkinter 置顶透明窗口，Pillow 抠图（品红透明键 + 边缘羽化，不冒紫光）
- 拖动移动、单击互动（弹跳 + 台词气泡）、双击旋转视角、双击右键 / Esc 关闭
- 素材沿用 `web/public/lulu/1~7.png`（7 张噜噜形象）

---

## 配色

`capylulu/ui/theme.py` 内置 7 套配色（噜噜黄为主），Web「设置」页一键切换；主题变量在 `web/src/styles/theme.css`。

---

## 常见问题

| 问题 | 处理 |
|------|------|
| 页面还是旧的 | 前端改动后需 `npm run build`；浏览器 Ctrl+F5 强刷 |
| 桌宠打不开 | 确认 `web/public/lulu/` 存在 1~7.png（pet.py 素材路径） |
| 端口 6661 被占 | `netstat -ano | findstr 6661` 找到 PID，结束后重试 |
| 模型不回复 | 检查 `config.yaml` 的 api_key 与 provider 是否有效 |
| MCP 工具不出现 | 确认服务已启用并「测试连接」刷新动态注册 |

---

## 许可证

个人项目。使用前请替换 `config.yaml` 中的 API Key；噜噜形象图 / 水豚素材为项目自寻素材，商用请自行确认版权。

