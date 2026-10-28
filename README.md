# Capylulu · 噜噜

**多管家协作的桌面 AI 助手，佛系淡定帮你操作电脑。**

Capylulu（噜噜）是一个基于 Python 的桌面 AI 助手。以 **Leader 主理人 + 管家 Agent 团队** 的模式运行：主理人理解你的意图，分派给对应管家执行——文件管家管文件、电脑管家查系统、浏览器专员上网抓内容。对话、记忆、定时任务、桌宠、七套配色切换，一条 `python run.py` 全搞定。

---

## 设计哲学

**LLM 决定"做什么"，管家团队决定"谁来做"，工具决定"怎么做"。**

| 层级 | 组成 | 类比 |
| :--- | :--- | :--- |
| `capylulu/agent/` | Leader 主理人 + 管家 Agent（意图路由、规划、循环执行） | **店长 + 店员** |
| `capylulu/tools/` | 工具注册表 + 安全分级（文件 / 系统 / 桌面 / 键鼠） | **工具箱** |
| `capylulu/server_api/` | FastAPI 薄层，暴露 REST API | **柜台** |
| `web/` | Vue 3 前端（导航轨 + 平台状态面板 + 内容区） | **门面** |

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

## 核心能力

### 1. 规划引擎与能力路由

- **三模式决策**：Chat（纯聊天）、Direct（单执行者）、Plan（多步骤协作）
- **步骤依赖**：plan 的每个 step 可声明 `depends`（前置步骤序号）
- **失败重试与降级**：单步失败自动重试 1 次；全部失败降级为 Leader 全量工具直接处理

### 2. 管家团队

内置管家：

| 管家 | 职责 | 主要工具 |
|------|------|----------|
| 文件管家 | 读、写、搜、整理文件 | read_file / write_file / search_files / move_file |
| 电脑管家 | 系统信息、磁盘、时间、设置 | system_info / disk_usage / now_datetime |
| 浏览器专员 | 打开网页、抓取摘要 | open_url / fetch_page |

- 持久化在 `data/agents.json`，支持增删改、启停
- 委派失败自动升级机制（重试 → 按能力转交 → Leader 兜底）

### 3. 技能运行时（SKILL.md）

- 技能文件位于 `data/skills/<技能名>.md`
- 支持解析 / 列表 / 执行技能
- 5 个内置技能自动生成（文件整理、文档搜索、图片搜索、发票识别、图片处理）

### 4. MCP 生态

- 支持 stdio / SSE / HTTP 三种连接方式
- MCP 市场内置常见服务（filesystem / fetch / memory / time 等）
- 工具动态注册，命名 `mcp_<server>_<tool>`

### 5. 三级记忆与深度蒸馏

| 层级 | 目录 | 内容 |
|------|------|------|
| 工作记忆 | `data/memory/working/` | 会话级上下文 |
| 情景记忆 | `data/memory/episodic/` | 结构化事件记录 |
| 语义记忆 | `data/memory/semantic/` | 蒸馏后的长期知识 |

### 6. 知识库

- 支持 txt / md / csv / json / pdf 等格式导入
- 中文分词 + TF-IDF 检索
- LLM 问答（基于检索片段生成回答）

### 7. 桌面操作工具

- **窗口管理**：window_list / window_activate / window_minimize / window_maximize / window_close
- **进程管理**：process_list / process_kill（白名单保护）
- **媒体控制**：volume_get / volume_set / brightness_set
- **屏幕与键鼠**：screenshot / key_simulate（仅白名单组合）

### 8. IM 通道

- 支持 Webhook（钉钉 / 企业微信群机器人）
- 本地接收通道（模拟推送）
- 消息中心统一处理收发光

### 9. 自主进化

- **经验库**：记录成功经验与失败教训
- **反思引擎**：从任务台账批量反思
- **自我改进**：低风险建议自动应用，高风险建议待人工确认

---

## 快速开始

### 环境准备

- Windows 10/11
- Python 3.11+
- Node.js 18+（前端构建用）

### 安装依赖

```bash
git clone <your-repo>/capylulu-agent.git
cd capylulu-agent
pip install -r requirements.txt
```

### 配置

复制配置模板并填写 API Key：

```bash
copy config.example.yaml config.yaml
```

编辑 `config.yaml`，填入 LLM API Key：

```yaml
llm:
  provider: zhipu        # 或 deepseek
  zhipu:
    api_key: sk-xxx
    base_url: https://open.bigmodel.cn/api/paas/v4/
    model: glm-4-flash
```

### 启动

```bash
python run.py
```

访问 `http://127.0.0.1:6661`

### 开发模式

```bash
# 后端 API
python -m uvicorn capylulu.server_api.main:app --host 0.0.0.0 --port 6661

# 前端热更新
cd web && npm install && npm run dev
```

---

## 目录结构

```
capylulu/
├── run.py                  # 一键启动入口
├── requirements.txt        # 后端依赖
├── config.example.yaml     # 配置模板
│
├── capylulu/               # 核心包
│   ├── agent/              # Leader 主理人 + 管家 Agent
│   ├── llm/                # LLM 客户端
│   ├── skills/             # 技能运行时
│   ├── mcp/                # MCP 生态
│   ├── memory3/            # 三级记忆
│   ├── kb/                 # 知识库
│   ├── team/               # 管家团队任务台账
│   ├── evolve/             # 自主进化
│   ├── im/                 # IM 通道
│   ├── tools/              # 工具注册表
│   ├── server_api/         # FastAPI 层
│   ├── ui/                 # 配色主题
│   └── ...
│
├── web/                    # 前端（Vue 3 + Vite）
│   ├── src/
│   │   ├── views/          # 12 个视图
│   │   ├── router/         # 路由配置
│   │   └── styles/         # 主题样式
│   └── public/             # 静态资源
│
└── data/                   # 运行时数据
```

---

## 常见问题

| 问题 | 处理 |
|------|------|
| 页面还是旧的 | 前端改动后需 `npm run build`；浏览器 Ctrl+F5 强刷 |
| 桌宠打不开 | 确认 `web/public/lulu/` 存在素材图片 |
| 端口 6661 被占 | `netstat -ano \| findstr 6661` 找到 PID 结束 |
| 模型不回复 | 检查 `config.yaml` 的 api_key 与 provider |
| MCP 工具不出现 | 确认服务已启用并刷新动态注册 |

---

## 许可证

个人项目。使用前请替换 `config.yaml` 中的 API Key。