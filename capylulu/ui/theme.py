"""界面主题：内置多套市面常见配色，通过 CSS 变量切换。
UI v3：现代 AI 助手工作台风格（Marvis/Doubao/WorkBuddy 参考），毛玻璃侧栏 220px、顶栏标题卡、居中对话流 860px、大圆角分层阴影主色渐变，Dataframe/Accordion/日志/表单全量升级。"""
# 下拉显示名 → CSS 变量（可在设置页随时换）
PALETTES = {
    "琥珀暖暗": {  # 默认，比纯黑更暖
        "--capy-bg": "#2B2722",
        "--capy-sidebar": "#241F1B",
        "--capy-card": "#35302A",
        "--capy-card2": "#3F3932",
        "--capy-border": "#4A433B",
        "--capy-text": "#F4EDE4",
        "--capy-text2": "#B8AFA4",
        "--capy-yellow": "#FFC940",
        "--capy-yellow-dark": "#FFB820",
        "--capy-user-bg": "rgba(255,201,64,0.22)",
        "--capy-bot-bg": "#3A342E",
    },
    "Nord": {
        "--capy-bg": "#2E3440",
        "--capy-sidebar": "#242933",
        "--capy-card": "#3B4252",
        "--capy-card2": "#434C5E",
        "--capy-border": "#4C566A",
        "--capy-text": "#ECEFF4",
        "--capy-text2": "#D8DEE9",
        "--capy-yellow": "#88C0D0",
        "--capy-yellow-dark": "#81A1C1",
        "--capy-user-bg": "rgba(136,192,208,0.25)",
        "--capy-bot-bg": "#3B4252",
    },
    "Catppuccin Mocha": {
        "--capy-bg": "#1E1E2E",
        "--capy-sidebar": "#181825",
        "--capy-card": "#313244",
        "--capy-card2": "#45475A",
        "--capy-border": "#585B70",
        "--capy-text": "#CDD6F4",
        "--capy-text2": "#A6ADC8",
        "--capy-yellow": "#F9E2AF",
        "--capy-yellow-dark": "#FAB387",
        "--capy-user-bg": "rgba(249,226,175,0.22)",
        "--capy-bot-bg": "#313244",
    },
    "Tokyo Night": {
        "--capy-bg": "#1A1B26",
        "--capy-sidebar": "#16161E",
        "--capy-card": "#24283B",
        "--capy-card2": "#2F3549",
        "--capy-border": "#414868",
        "--capy-text": "#C0CAF5",
        "--capy-text2": "#9AA5CE",
        "--capy-yellow": "#7AA2F7",
        "--capy-yellow-dark": "#7DCFFF",
        "--capy-user-bg": "rgba(122,162,247,0.25)",
        "--capy-bot-bg": "#24283B",
    },
    "Solarized Dark": {
        "--capy-bg": "#002B36",
        "--capy-sidebar": "#00212B",
        "--capy-card": "#073642",
        "--capy-card2": "#0A4452",
        "--capy-border": "#586E75",
        "--capy-text": "#FDF6E3",
        "--capy-text2": "#93A1A1",
        "--capy-yellow": "#B58900",
        "--capy-yellow-dark": "#CB4B16",
        "--capy-user-bg": "rgba(181,137,0,0.28)",
        "--capy-bot-bg": "#073642",
    },
    "GitHub Light": {
        "--capy-bg": "#F6F8FA",
        "--capy-sidebar": "#FFFFFF",
        "--capy-card": "#FFFFFF",
        "--capy-card2": "#F0F3F6",
        "--capy-border": "#D0D7DE",
        "--capy-text": "#1F2328",
        "--capy-text2": "#656D76",
        "--capy-yellow": "#D4A017",
        "--capy-yellow-dark": "#BF8C0A",
        "--capy-user-bg": "rgba(212,160,23,0.18)",
        "--capy-bot-bg": "#F0F3F6",
    },
    "暖米浅色": {
        "--capy-bg": "#F7F1E8",
        "--capy-sidebar": "#EFE6D8",
        "--capy-card": "#FFFBF5",
        "--capy-card2": "#F3EADF",
        "--capy-border": "#E0D4C4",
        "--capy-text": "#3A3228",
        "--capy-text2": "#7A6E62",
        "--capy-yellow": "#E0A106",
        "--capy-yellow-dark": "#C78B00",
        "--capy-user-bg": "rgba(224,161,6,0.20)",
        "--capy-bot-bg": "#F3EADF",
    },
}

PALETTE_NAMES = list(PALETTES.keys())
DEFAULT_PALETTE = "琥珀暖暗"


def palette_style_html(name: str) -> str:
    """生成覆盖 :root 变量的一段 HTML，切配色时注入页面。"""
    p = PALETTES.get(name, PALETTES[DEFAULT_PALETTE])
    body = ";".join(f"{k}:{v}" for k, v in p.items())
    return f"<style>:root{{{body}}}</style>"


# 布局 / 气泡 / 隐藏 Gradio 默认工具条（依赖上面的 CSS 变量）
CUSTOM_CSS = """
:root {
  --capy-bg: #2B2722;
  --capy-sidebar: #241F1B;
  --capy-card: #35302A;
  --capy-card2: #3F3932;
  --capy-border: #4A433B;
  --capy-text: #F4EDE4;
  --capy-text2: #B8AFA4;
  --capy-yellow: #FFC940;
  --capy-yellow-dark: #FFB820;
  --capy-user-bg: rgba(255,201,64,0.22);
  --capy-bot-bg: #3A342E;

  /* UI v3 设计 Token：大圆角 / 分层阴影 / 毛玻璃 / 主色渐变（全部随 7 套配色自动推导） */
  --capy-radius-sm: 10px;
  --capy-radius-md: 14px;
  --capy-radius-lg: 20px;
  --capy-radius-xl: 24px;
  --capy-radius-pill: 999px;
  --capy-shadow-xs: 0 1px 2px rgba(0,0,0,.18);
  --capy-shadow-card: 0 2px 8px rgba(0,0,0,.14), 0 8px 24px rgba(0,0,0,.10);
  --capy-shadow-hover: 0 8px 28px rgba(0,0,0,.26);
  --capy-shadow-pop: 0 8px 16px rgba(0,0,0,.18), 0 20px 48px rgba(0,0,0,.16);
  --capy-glass-bg: color-mix(in srgb, var(--capy-card) 82%, transparent);
  --capy-glass-sidebar: color-mix(in srgb, var(--capy-sidebar) 88%, transparent);
  --capy-grad: linear-gradient(135deg, var(--capy-yellow), var(--capy-yellow-dark));
  --capy-border-soft: color-mix(in srgb, var(--capy-border) 85%, transparent);
  --capy-transition: all .18s cubic-bezier(.4,0,.2,1);
  --capy-primary-soft: color-mix(in srgb, var(--capy-yellow) 12%, transparent);
  --capy-primary-soft2: color-mix(in srgb, var(--capy-yellow) 6%, transparent);
  --capy-primary-border: color-mix(in srgb, var(--capy-yellow) 35%, transparent);
  --capy-primary-glow: color-mix(in srgb, var(--capy-yellow) 25%, transparent);
  --capy-danger: #E5484D;
  --capy-danger-bg: color-mix(in srgb, var(--capy-danger) 14%, transparent);
  --capy-danger-border: color-mix(in srgb, var(--capy-danger) 45%, transparent);
  --capy-font-mono: ui-monospace, Consolas, "Cascadia Mono", "Courier New", monospace;
}
* { box-sizing: border-box; }
html, body { background: var(--capy-bg) !important; }
footer { display: none !important; }

.gradio-container {
  background:
    radial-gradient(1400px 700px at 18% -12%, var(--capy-primary-glow), transparent 55%),
    radial-gradient(900px 500px at 100% 0%, var(--capy-primary-soft2), transparent 60%),
    var(--capy-bg) !important;
  max-width: 100% !important;
  width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
  min-height: 100vh !important;
  height: 100vh !important;
  font-family: "Segoe UI", "Microsoft YaHei", "Noto Sans SC", sans-serif !important;
  color: var(--capy-text) !important;
}
#app-shell {
  min-height: 100vh !important;
  height: 100vh !important;
  gap: 0 !important;
  flex-wrap: nowrap !important;
  align-items: stretch !important;
}

/* 页面级标题：WorkBuddy 风顶栏卡（标题 + 渐变分隔线 + 底部细线） */
.capy-page-title h2 {
  position: relative !important;
  display: flex !important;
  align-items: center !important;
  gap: 10px !important;
  margin: 0 0 14px 0 !important;
  padding: 6px 0 14px 0 !important;
  font-size: 20px !important;
  font-weight: 800 !important;
  letter-spacing: .3px !important;
  color: var(--capy-text) !important;
  border-bottom: 1px solid color-mix(in srgb, var(--capy-border) 60%, transparent) !important;
}
.capy-page-title h2::after {
  content: "" !important;
  position: absolute !important;
  left: 0 !important; bottom: -1px !important;
  width: 48px !important; height: 3px !important;
  border-radius: var(--capy-radius-pill) !important;
  background: var(--capy-grad) !important;
}

#sidebar {
  background: var(--capy-glass-sidebar) !important;
  backdrop-filter: blur(16px) saturate(1.15) !important;
  -webkit-backdrop-filter: blur(16px) saturate(1.15) !important;
  border-right: 1px solid var(--capy-border-soft) !important;
  padding: 14px 14px 18px 14px !important;
  min-height: 100vh !important;
  max-height: 100vh !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  flex: 0 0 240px !important;
  width: 240px !important;
  min-width: 240px !important;
  max-width: 240px !important;
  gap: 10px !important;
}
#sidebar-logo, #welcome-img, #mascot-tools, #mascot-settings,
#mascot-team, #mascot-skills, #mascot-tasks, #mascot-local {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
#sidebar-logo {
  text-align: center !important;
  width: 88px !important;
  height: 88px !important;
  margin: 8px auto 4px auto !important;
  border-radius: 50% !important;
  overflow: hidden !important;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--capy-yellow) 30%, transparent), 0 8px 24px rgba(0,0,0,.25) !important;
}
.mascot-wrap { background: transparent !important; border: none !important; }
.mascot-wrap img { display: block !important; margin: 0 auto !important; }

#sidebar-title { text-align: center !important; margin: 6px 0 8px 0 !important; }
#sidebar-title h1 {
  font-size: 22px !important; font-weight: 800 !important;
  color: var(--capy-text) !important; margin: 0 !important;
}
#sidebar-title p { font-size: 11.5px !important; color: color-mix(in srgb, var(--capy-text2) 82%, transparent) !important; margin: 4px 0 0 0 !important; }

#btn-new {
  background: var(--capy-grad) !important;
  color: #2A2110 !important; font-weight: 700 !important;
  border: none !important; border-radius: var(--capy-radius-pill) !important;
  padding: 12px !important; font-size: 15px !important;
  box-shadow: var(--capy-shadow-card) !important;
}
#btn-new:hover { filter: brightness(1.06) !important; transform: translateY(-1px) !important; }

/* 桌宠按钮：描边胶囊，与实心渐变的新建按钮区分，hover 提亮 */
#btn-pet {
  background: var(--capy-glass-bg) !important;
  color: var(--capy-yellow) !important;
  border: 1.5px solid var(--capy-primary-border) !important;
  border-radius: var(--capy-radius-pill) !important;
  padding: 10px 12px !important; font-size: 14px !important; font-weight: 600 !important;
  box-shadow: var(--capy-shadow-card) !important;
}
#btn-pet:hover {
  background: var(--capy-primary-soft) !important;
  border-color: var(--capy-yellow) !important;
  filter: brightness(1.08) !important;
  transform: translateY(-1px) !important;
}

#nav-radio { background: transparent !important; border: none !important; }
#nav-radio label {
  display: flex !important; align-items: center !important; gap: 10px !important;
  padding: 10px 14px !important; border-radius: 12px !important;
  cursor: pointer !important; font-size: 14px !important;
  color: var(--capy-text2) !important; border: 1px solid transparent !important;
  margin-bottom: 4px !important;
  transition: var(--capy-transition) !important;
}
#nav-radio label:hover { background: var(--capy-primary-soft2) !important; color: var(--capy-text) !important; }
#nav-radio label:has(input:checked) {
  background: var(--capy-primary-soft) !important;
  color: var(--capy-yellow) !important;
  border-color: var(--capy-primary-border) !important;
  font-weight: 600 !important;
  box-shadow: inset 3px 0 0 var(--capy-yellow) !important;
}
#nav-radio input { accent-color: var(--capy-yellow) !important; }
#nav-radio span { color: inherit !important; }

/* 侧栏表单控件：下拉/输入统一圆角卡片风 */
#hist-row {
  align-items: stretch !important;
  gap: 6px !important;
}
#hist-row .dropdown,
#sidebar .dropdown,
#sidebar .wrap,
#sidebar .form {
  background: var(--capy-glass-bg) !important;
  border-radius: 12px !important;
}
#sidebar .dropdown {
  border: 1px solid var(--capy-border-soft) !important;
  color: var(--capy-text) !important;
}
#sidebar .dropdown:hover { border-color: var(--capy-primary-border) !important; }
#sidebar label span {
  color: var(--capy-text2) !important;
  font-size: 11.5px !important;
  font-weight: 600 !important;
}
#sidebar .dropdown button {
  color: var(--capy-text) !important;
  background: transparent !important;
}
#sidebar .dropdown ul {
  background: var(--capy-glass-bg) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: 12px !important;
  backdrop-filter: blur(14px) !important;
  box-shadow: var(--capy-shadow-pop) !important;
}
#sidebar .dropdown ul li:hover { background: var(--capy-primary-soft) !important; }
#sidebar .dropdown ul li[data-value="true"],
#sidebar .dropdown ul li.selected { background: var(--capy-primary-soft) !important; color: var(--capy-yellow) !important; }
#btn-hist-del {
  background: var(--capy-danger-bg) !important;
  color: var(--capy-danger) !important;
  border: 1px solid var(--capy-danger-border) !important;
  border-radius: 12px !important;
}
#btn-hist-del:hover { filter: brightness(1.12) !important; }
#btn-hist-menu, #btn-hist-rename {
  background: var(--capy-glass-bg) !important;
  color: var(--capy-text2) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: 12px !important;
  min-width: 42px !important;
  padding: 6px 0 !important;
}
#btn-hist-menu:hover, #btn-hist-rename:hover {
  border-color: var(--capy-primary-border) !important;
  color: var(--capy-yellow) !important;
}
#hist-ops {
  align-items: center !important;
  gap: 6px !important;
  padding: 0 2px !important;
}
#hist-ops .block,
#hist-ops .wrap {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
#hist-ops textarea {
  min-height: 0 !important;
  font-size: 12.5px !important;
  border-radius: 10px !important;
  padding: 6px 10px !important;
}
#hist-del-status p { font-size: 12px !important; }

#sidebar-footer {
  margin-top: auto !important;
  background: var(--capy-glass-bg) !important;
  backdrop-filter: blur(12px) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: 14px !important;
  padding: 10px 14px !important;
  box-shadow: var(--capy-shadow-card) !important;
}
#sidebar-footer p { font-size: 12px !important; color: var(--capy-text2) !important; margin: 0 !important; }

#main-col {
  background: var(--capy-bg) !important;
  padding: 0 !important;
  min-height: 100vh !important;
  height: 100vh !important;
  flex: 1 1 auto !important;
  display: flex !important;
  flex-direction: column !important;
}
.view-col {
  padding: 20px 28px 28px 28px !important;
  gap: 16px !important;
  flex: 1 1 auto !important;
  min-height: 0 !important;
  height: 100% !important;
  display: flex !important;
  flex-direction: column !important;
  overflow-y: auto !important;  /* 板块内容超高时可滚动，避免按钮/表单被挤出不可点 */
}

#welcome-card {
  background: linear-gradient(135deg, var(--capy-primary-soft), var(--capy-primary-soft2)) !important;
  border: 1px solid color-mix(in srgb, var(--capy-yellow) 25%, transparent) !important;
  border-radius: var(--capy-radius-xl) !important;
  padding: 36px 44px !important;
  max-width: 860px !important;
  width: 100% !important;
  margin: 24px auto !important;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--capy-yellow) 25%, transparent), 0 12px 40px rgba(0,0,0,.18) !important;
}
#welcome-card h1 { font-size: 28px !important; font-weight: 800 !important; color: var(--capy-text) !important; margin: 0 0 8px 0 !important; }
#welcome-card p { color: var(--capy-text2) !important; font-size: 14.5px !important; line-height: 1.7 !important; }
#welcome-card img { filter: drop-shadow(0 10px 28px rgba(255,201,64,.22)) !important; }
.capy-welcome {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

#chips-row { gap: 10px !important; justify-content: center !important; }
#chips-row button {
  background: color-mix(in srgb, var(--capy-card2) 85%, transparent) !important;
  border: 1px solid var(--capy-border-soft) !important;
  color: var(--capy-text) !important; border-radius: var(--capy-radius-pill) !important;
  padding: 8px 16px !important; font-size: 13px !important;
  transition: var(--capy-transition) !important;
}
#chips-row button:hover {
  border-color: var(--capy-yellow) !important; color: var(--capy-yellow) !important;
  background: var(--capy-primary-soft) !important;
}

/* ===== 聊天消息流（严格按 gradio 6.30 真实 DOM 编写）=====
   真实 DOM：
     .message-wrap (flex column)
       └ .message-row.bubble.user-row | .message-row.bubble.bot-row
           ├ .avatar-container                          （有头像时才有）
           └ .flex-wrap → .message.user | .message.bot   ← 真正的气泡
   关键结论：.bubble 就是 .message-row 本身，不是内层气泡！
   之前把 .bubble 当气泡改 width/max-width，又给 .flex-wrap 加 fit-content 上限，
   两者互相挤压，才出现"两个字一行 + 气泡忽大忽小 + 行高被拉满"。
   Gradio 原生已按内容自适应宽度（行 align-self + max-width: calc(100% - 12rem)），
   所以这里只做配色与排版，不再覆盖任何 width / overflow-wrap。 */

#chat-area {
  background: var(--capy-card) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: var(--capy-radius-lg) !important;
  /* 占满主栏剩余高度（配合 .view-col 的 flex 列），滚动交给内部 .bubble-wrap；
     不再用 calc(100vh - 250px) 固定高度，避免把输入行挤出可视区。 */
  flex: 1 1 auto !important;
  min-height: 240px !important;
  height: auto !important;
  max-height: 100% !important;
  overflow: hidden !important;
  max-width: 860px !important;
  width: 100% !important;
  margin: 0 auto !important;
  box-shadow: var(--capy-shadow-card) !important;
}
/* Chatbot 外层 wrap 不重复叠背景/边框，避免盖住气泡流 */
#chat-area .wrap,
#chat-area .block {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
#chat-area .icon-button, #chat-area button.icon-button,
#chat-area [class*="icon-button"], #chat-area .copy-text,
#chat-area button[aria-label*="Share"],
#chat-area button[aria-label*="Copy"],
#chat-area button[aria-label*="Delete"],
#chat-area button[aria-label*="share"],
#chat-area button[aria-label*="copy"],
#chat-area button[aria-label*="Clear"] {
  display: none !important;
}
/* 滚动容器：只补内边距，纵向布局与宽度交给 Gradio 原生 */
#chat-area .bubble-wrap {
  background: transparent !important;
  padding: 14px 18px !important;
}
/* 不再使用 [class*="flex-wrap"] 通配选择器：会误伤 Chatbot 消息内容内部的
   其它 flex-wrap 子元素（如 markdown 渲染的 flex 布局），造成内容被纵向排列。 */
/* 消息行：只补间距与对齐，宽度完全交给 Gradio 原生（勿设 max-width/flex） */
#chat-area .message-row {
  margin: 10px 4px !important;
}
/* 用户侧不显示头像（avatar_images 用户位为 None 时 Gradio 会画占位圆圈）*/
#chat-area .message-row.user-row > .avatar-container {
  display: none !important;
}
#chat-area .avatar-container {
  flex-shrink: 0 !important;
}

/* 真正的气泡：.message.user / .message.bot —— 只做外观，不碰宽度 */
#chat-area .message.user,
#chat-area .message.bot {
  border-radius: var(--capy-radius-lg) !important;
  padding: 10px 16px !important;
  font-size: 15px !important;
  line-height: 1.65 !important;
  color: var(--capy-text) !important;
  box-shadow: none !important;
  /* 中文按词换行：任何 overflow-wrap:anywhere 都会把汉字拆成两个字一行 */
  word-break: normal !important;
  overflow-wrap: break-word !important;
}
#chat-area .message.bot {
  background: var(--capy-bot-bg) !important;
  border: 1px solid var(--capy-border-soft) !important;
}
#chat-area .message.user {
  background: var(--capy-user-bg) !important;
  border: 1px solid var(--capy-yellow) !important;
}

/* 气泡内部（markdown 外壳 / 内层 .message）不要再叠一层底色和边框，
   否则会出现"气泡下面多一个空色块" */
#chat-area .message .message,
#chat-area .message .prose,
#chat-area .message .html {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}
#chat-area .message:empty { display: none !important; }
#chat-area .prose,
#chat-area .message p,
#chat-area .bot p, #chat-area .user p {
  color: inherit !important;
  margin: 0 !important;
}
#chat-area .prose p:not(:first-child) { margin-top: 8px !important; }
/* 代码块与表格：允许内部滚动但绝不撑破聊天区宽度 */
#chat-area .prose pre {
  white-space: pre !important;
  overflow-x: auto !important;
  max-width: 100% !important;
}
#chat-area .prose table {
  display: block !important;
  max-width: 100% !important;
  overflow-x: auto !important;
}
#chat-area .prose img {
  max-width: 100% !important;
  height: auto !important;
}

#input-row {
  background: color-mix(in srgb, var(--capy-card) 85%, transparent) !important;
  backdrop-filter: blur(12px) !important;
  -webkit-backdrop-filter: blur(12px) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: var(--capy-radius-xl) !important;
  padding: 10px 12px !important;
  align-items: center !important;
  gap: 8px !important;
  flex: 0 0 auto !important;
  max-width: 860px !important;
  width: 100% !important;
  margin: 16px auto 0 auto !important;
  position: relative !important;
  box-shadow: var(--capy-shadow-card) !important;
  transition: border-color .18s ease, box-shadow .18s ease !important;
}
/* 顶部渐变分隔线：强化输入区与聊天区的边界层次 */
#input-row::before {
  content: "" !important;
  position: absolute !important;
  top: -9px !important;
  left: 14% !important;
  right: 14% !important;
  height: 1px !important;
  border-radius: 2px !important;
  background: linear-gradient(90deg, transparent, var(--capy-yellow) 30%, var(--capy-yellow) 70%, transparent) !important;
  opacity: .5 !important;
}
#input-row:focus-within {
  border-color: var(--capy-yellow) !important;
  box-shadow: 0 0 0 3px var(--capy-primary-glow), var(--capy-shadow-card) !important;
}
#btn-send {
  background: var(--capy-grad) !important;
  color: #2A2110 !important; font-weight: 700 !important;
  border: none !important; border-radius: 14px !important;
  height: 44px !important; min-width: 92px !important;
  box-shadow: var(--capy-shadow-card) !important;
}
#btn-send:hover { filter: brightness(1.07) !important; transform: translateY(-1px) !important; }

/* 加载动画：发送后、回复前显示的三点跳动指示 */
#loading-indicator {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 8px !important;
  padding: 10px 0 !important;
  color: var(--capy-text2) !important;
  font-size: 13px !important;
}
#loading-indicator .dot {
  width: 8px !important;
  height: 8px !important;
  border-radius: 50% !important;
  background: var(--capy-yellow) !important;
  animation: capy-bounce 1.2s infinite ease-in-out !important;
}
#loading-indicator .dot:nth-child(2) { animation-delay: .15s !important; }
#loading-indicator .dot:nth-child(3) { animation-delay: .3s !important; }
@keyframes capy-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: .4; }
  40% { transform: translateY(-6px); opacity: 1; }
}

textarea, input[type="text"], input[type="password"], input:not([type]) {
  background: var(--capy-card2) !important;
  border: 1px solid var(--capy-border-soft) !important;
  color: var(--capy-text) !important;
  border-radius: 16px !important;
  font-size: 14px !important;
  transition: var(--capy-transition) !important;
}
textarea::placeholder, input::placeholder { color: color-mix(in srgb, var(--capy-text2) 60%, transparent) !important; }
textarea:focus, input:focus {
  border-color: var(--capy-yellow) !important;
  box-shadow: 0 0 0 3px var(--capy-primary-glow) !important;
}
.gradio-container label span { color: var(--capy-text2) !important; font-size: 13px !important; }
.gradio-container button.secondary {
  background: var(--capy-card2) !important;
  color: var(--capy-text) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: var(--capy-radius-md) !important;
}
/* UI v3 统一按钮：主色渐变、圆角、分层阴影、过渡 */
.gradio-container button {
  min-height: 40px !important;
  transition: var(--capy-transition) !important;
  box-shadow: var(--capy-shadow-card) !important;
}
/* 下拉/选择器内部按钮保持原生紧凑尺寸，防止 min-height 撑高破坏可点性 */
.gradio-container .dropdown button,
.gradio-container .radio button,
.gradio-container .checkbox button {
  min-height: 0 !important;
  box-shadow: none !important;
  transform: none !important;
}
.gradio-container button:hover { transform: translateY(-1px) !important; box-shadow: var(--capy-shadow-hover) !important; filter: brightness(1.04) !important; }
.gradio-container button:active { transform: translateY(0) !important; }
.gradio-container button.primary {
  background: var(--capy-grad) !important;
  border: none !important;
  color: var(--capy-bg) !important;
  font-weight: 700 !important;
  border-radius: var(--capy-radius-md) !important;
  padding: 10px 18px !important;
  text-shadow: 0 1px 0 rgba(255,255,255,.18) !important;
}
.gradio-container button.stop {
  background: var(--capy-danger-bg) !important;
  color: var(--capy-danger) !important;
  border: 1px solid var(--capy-danger-border) !important;
  font-weight: 600 !important;
  border-radius: var(--capy-radius-md) !important;
}
.gradio-container button.stop:hover { background: var(--capy-danger) !important; color: #fff !important; }
.gradio-container button.secondary:hover { border-color: var(--capy-primary-border) !important; color: var(--capy-yellow) !important; background: var(--capy-primary-soft2) !important; }

/* 表单容器：label、dropdown、checkbox 统一配色 */
.gradio-container .block,
.gradio-container .form,
.gradio-container .wrap {
  background: var(--capy-card) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: var(--capy-radius-md) !important;
}
.gradio-container .dropdown,
.gradio-container .dropdown .wrap {
  background: var(--capy-card2) !important;
  border-radius: var(--capy-radius-sm) !important;
}
.gradio-container .dropdown button { color: var(--capy-text) !important; }
.gradio-container .dropdown .wrap:hover { border-color: var(--capy-primary-border) !important; }
.gradio-container .dropdown ul {
  background: var(--capy-glass-bg) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: var(--capy-radius-sm) !important;
  backdrop-filter: blur(14px) !important;
  box-shadow: var(--capy-shadow-pop) !important;
}
.gradio-container .dropdown ul li { color: var(--capy-text) !important; }
.gradio-container .dropdown ul li:hover { background: var(--capy-primary-soft) !important; }
.gradio-container .dropdown ul li[data-value="true"],
.gradio-container .dropdown ul li.selected { background: var(--capy-primary-soft) !important; color: var(--capy-yellow) !important; font-weight: 600 !important; }

/* capy-panel：板块内部内容分组卡片（UI v4 卡片组，Marvis 工作台风） */
.capy-panel {
  background: var(--capy-card) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: var(--capy-radius-lg) !important;
  padding: 24px 28px !important;
  box-shadow: var(--capy-shadow-card) !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 14px !important;
  transition: var(--capy-transition) !important;
}
.capy-panel:hover {
  border-color: var(--capy-primary-border) !important;
  box-shadow: var(--capy-shadow-hover) !important;
}

/* capy-section：内容区小节标题（左侧 3px 主色渐变竖条，替换裸 ### Markdown） */
.capy-section {
  position: relative !important;
  margin: 2px 0 10px 0 !important;
  padding-left: 12px !important;
}
.capy-section::before {
  content: "" !important;
  position: absolute !important;
  left: 0 !important;
  top: 2px !important;
  bottom: 2px !important;
  width: 3px !important;
  border-radius: var(--capy-radius-pill) !important;
  background: var(--capy-grad) !important;
  opacity: .85 !important;
}
.capy-section h3 {
  font-size: 12.5px !important;
  font-weight: 700 !important;
  color: var(--capy-text2) !important;
  margin: 0 !important;
  letter-spacing: .3px !important;
}

/* Dataframe：表头/单元格/滚动条整体质感 */
.capy-df {
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: 16px !important;
  overflow: hidden !important;
  background: var(--capy-card) !important;
  box-shadow: var(--capy-shadow-card) !important;
}
.capy-df .table-wrap,
.capy-df .wrap {
  background: var(--capy-card) !important;
  border: none !important;
  border-radius: 16px !important;
}
.capy-df table { border-collapse: separate !important; border-spacing: 0 !important; }
.capy-df thead th {
  background: var(--capy-card2) !important;
  color: var(--capy-text2) !important;
  font-weight: 600 !important;
  font-size: 13px !important;
  border-bottom: 1px solid var(--capy-border-soft) !important;
  padding: 10px 14px !important;
  white-space: nowrap !important;
}
.capy-df tbody td {
  color: var(--capy-text) !important;
  border-bottom: 1px solid var(--capy-border-soft) !important;
  padding: 9px 14px !important;
  font-size: 13.5px !important;
}
.capy-df tbody tr:nth-child(even) { background: color-mix(in srgb, var(--capy-card2) 60%, transparent) !important; }
.capy-df tbody tr:hover { background: color-mix(in srgb, var(--capy-yellow) 8%, transparent) !important; }
.capy-df label span,
.capy-df .label-wrap span { color: var(--capy-text) !important; font-weight: 700 !important; }

/* 日志区（任务列表 / 执行记录 / 工具记录） */
.capy-log {
  background: var(--capy-card) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: var(--capy-radius-md) !important;
  font-family: var(--capy-font-mono) !important;
  font-size: 12.5px !important;
  line-height: 1.7 !important;
  color: var(--capy-text) !important;
  box-shadow: var(--capy-shadow-card) !important;
  padding: 14px 18px !important;
}
.capy-log textarea {
  background: var(--capy-card) !important;
  border: none !important;
  box-shadow: none !important;
  color: var(--capy-text) !important;
}

/* 状态提示（增删改结果回显） */
.capy-status p {
  font-size: 13px !important;
  color: var(--capy-text2) !important;
  background: var(--capy-primary-soft2) !important;
  border-left: 3px solid var(--capy-primary-border) !important;
  border-radius: 10px !important;
  padding: 8px 14px !important;
  margin: 2px 0 8px 0 !important;
}
.capy-status p:first-child { color: var(--capy-yellow) !important; }

/* Accordion：圆角卡片 + 主色箭头 */
.gradio-container .accordion {
  background: var(--capy-card) !important;
  border: 1px solid var(--capy-border-soft) !important;
  border-radius: var(--capy-radius-md) !important;
  box-shadow: var(--capy-shadow-card) !important;
  overflow: hidden !important;
  transition: var(--capy-transition) !important;
}
.gradio-container .accordion:hover { border-color: var(--capy-primary-border) !important; }
.gradio-container .accordion > button {
  background: var(--capy-card) !important;
  color: var(--capy-text) !important;
  font-weight: 700 !important;
  font-size: 14px !important;
  padding: 14px 18px !important;
  border: none !important;
  box-shadow: none !important;
}
.gradio-container .accordion > button:hover { background: var(--capy-primary-soft) !important; color: var(--capy-yellow) !important; }
.gradio-container .accordion .label-wrap { padding: 16px 18px !important; }

/* 细滚动条：6px、圆角、hover 主色半透明 */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: var(--capy-border); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: var(--capy-primary-border) !important; }
::-webkit-scrollbar-track { background: transparent !important; }
#palette-inject { display: none !important; height: 0 !important; }
"""
