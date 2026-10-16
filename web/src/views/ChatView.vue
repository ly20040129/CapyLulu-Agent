<template>
  <div class="chat-view">
    <!-- 会话列表栏 -->
    <aside class="hist-col">
      <div class="hist-head">
        <button class="btn btn-primary btn-block" @click="newChat">＋ 新对话</button>
      </div>
      <div class="hist-list">
        <div
          v-for="s in sessions" :key="s.id"
          class="hist-item" :class="{ active: s.id === currentId }"
          @click="openSession(s.id)"
        >
          <div class="hist-title">{{ s.title }}</div>
          <div class="hist-meta">{{ s.count }} 条 · {{ shortTime(s.created) }}</div>
          <div class="hist-menu" @click.stop>
            <button class="btn btn-ghost btn-icon btn-sm" @click="renamePrompt(s)" title="重命名"><img class="btn-icon-img" src="/lulu/6.png" alt="重命名" /></button>
            <button class="btn btn-ghost btn-icon btn-sm danger" @click="askDelete(s)" title="删除"><img class="btn-icon-img" src="/lulu/7.png" alt="删除" /></button>
          </div>
        </div>
      </div>
      <div class="hist-foot">
        <button class="btn btn-secondary btn-block btn-mascot" @click="callMascot"><img src="/lulu/3.png" alt="噜噜" class="btn-mascot-img" /> 召唤桌宠</button>
      </div>
    </aside>

    <!-- 对话区 -->
    <section class="chat-main">
      <div class="chat-scroll" ref="scrollRef">
        <div v-if="!messages.length" class="chat-empty">
          <div class="empty-logo"><img src="/lulu/1.png" alt="噜噜" /></div>
          <div class="empty-scene"><img src="/lulu/scenes/dino.png" alt="噜噜的日常" /></div>
          <div class="empty-title">噜噜 · 佛系桌面助手</div>
          <div class="empty-sub">有事说事，没事喝茶。我在旁边摸鱼待命。</div>
          <div class="empty-hints">
            <button v-for="h in hints" :key="h" class="btn btn-outline btn-sm" @click="send(h)">{{ h }}</button>
          </div>
        </div>

        <template v-else>
          <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
            <div class="msg-avatar"><img v-if="m.role === 'user'" src="/lulu/2.png" alt="我" class="avatar-img" /><img v-else src="/lulu/4.png" alt="噜噜" class="avatar-img" /></div>
            <div class="msg-bubble">{{ m.content }}</div>
          </div>
        </template>

        <div v-if="sending" class="msg-row assistant">
          <div class="msg-avatar"><img src="/lulu/4.png" alt="噜噜" class="avatar-img" /></div>
          <div class="llu-loading"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
        </div>
      </div>

      <!-- 输入行 -->
      <div class="chat-input-row">
        <div class="input-box">
          <textarea
            ref="inputRef"
            v-model="draft"
            class="chat-textarea"
            placeholder="和噜噜说点什么…（Enter 发送，Shift+Enter 换行）"
            @keydown.enter.exact.prevent="send()"
          ></textarea>
          <div class="input-actions">
            <span class="input-hint">{{ specialist }}</span>
            <button class="btn btn-primary btn-sm send-btn" :disabled="sending || !draft.trim()" @click="send()">
              {{ sending ? '…' : '发送 ➤' }}
            </button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref, nextTick } from 'vue'
import { chatApi, miscApi } from '../api'
import { toast } from '../composables/toast'

const sessions = ref([])
const currentId = ref('')
const messages = ref([])
const draft = ref('')
const sending = ref(false)
const specialist = ref('自动')
const scrollRef = ref(null)
const inputRef = ref(null)

const hints = ['帮我看看当前目录有什么文件', '这台电脑配置怎么样', '打开记事本', '现在几点啦']

const shortTime = (t) => {
  if (!t) return ''
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadSessions() {
  try {
    const r = await chatApi.sessions()
    sessions.value = r.items || []
  } catch (e) {
    toast('会话列表加载失败：' + e.message)
  }
}

async function newChat() {
  try {
    const s = await chatApi.createSession()
    currentId.value = s.id
    messages.value = []
    draft.value = ''
    await loadSessions()
    focusInput()
  } catch (e) {
    toast('新建会话失败：' + e.message)
  }
}

async function openSession(id) {
  currentId.value = id
  try {
    const r = await chatApi.getSession(id)
    messages.value = r.messages || []
    await nextTick()
    scrollBottom()
  } catch (e) {
    toast('加载会话失败：' + e.message)
  }
}

async function renamePrompt(s) {
  const title = window.prompt('新的标题：', s.title)
  if (!title || title === s.title) return
  try {
    await chatApi.rename(s.id, title)
    await loadSessions()
  } catch (e) {
    toast('重命名失败：' + e.message)
  }
}

function askDelete(s) {
  if (window.confirm(`确定删除会话「${s.title}」？删除后不可恢复。`)) {
    doDelete(s.id)
  }
}

async function doDelete(id) {
  try {
    await chatApi.del(id)
    if (currentId.value === id) { currentId.value = ''; messages.value = [] }
    await loadSessions()
    toast('会话已删除')
  } catch (e) {
    toast('删除失败：' + e.message)
  }
}

async function send(text) {
  const msg = (text ?? draft.value ?? '').trim()
  if (!msg || sending.value) return
  draft.value = ''
  messages.value = [...messages.value, { role: 'user', content: msg }]
  sending.value = true
  await nextTick()
  scrollBottom()
  try {
    const r = await chatApi.send(currentId.value, msg, specialist.value)
    messages.value = r.messages || [...messages.value, { role: 'assistant', content: r.reply }]
    if (r.session_id && r.session_id !== currentId.value) {
      currentId.value = r.session_id
      await loadSessions()
    }
  } catch (e) {
    messages.value = [...messages.value, { role: 'assistant', content: '噜噜这边卡了一下：' + e.message }]
  } finally {
    sending.value = false
    await nextTick()
    scrollBottom()
    focusInput()
  }
}

async function callMascot() {
  try {
    const r = await miscApi.mascotStart()
    toast(r.message || '桌宠已打开')
  } catch (e) {
    toast('桌宠启动失败：' + e.message)
  }
}

function scrollBottom() {
  if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
}
function focusInput() {
  if (inputRef.value) inputRef.value.focus()
}

onMounted(async () => {
  await loadSessions()
  focusInput()
})
</script>

<style scoped>
.chat-view { display: flex; height: 100%; }

.hist-col {
  width: 250px; flex: 0 0 auto;
  background: var(--capy-glass-sidebar);
  backdrop-filter: blur(14px);
  border-right: 1px solid var(--capy-border-soft);
  display: flex; flex-direction: column;
  padding: 12px;
}
.hist-head { padding-bottom: 10px; border-bottom: 1px solid var(--capy-border-soft); }
.btn-block { width: 100%; }
.hist-list { flex: 1; overflow-y: auto; margin-top: 10px; display: flex; flex-direction: column; gap: 4px; }
.hist-item {
  padding: 8px 10px;
  border-radius: var(--capy-radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition: var(--capy-transition);
  position: relative;
}
.hist-item:hover { background: var(--capy-primary-soft2); }
.hist-item.active { background: var(--capy-primary-soft); border-color: var(--capy-primary-border); }
.hist-title { font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 48px; }
.hist-meta { font-size: 11px; color: var(--capy-text2); margin-top: 2px; }
.hist-menu {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  display: none; gap: 2px;
}
.hist-item:hover .hist-menu { display: flex; }
.btn-icon-img { width: 14px; height: 14px; border-radius: 4px; object-fit: cover; display: block; }
.hist-menu .danger:hover { color: var(--capy-danger); }
.hist-foot { padding-top: 10px; border-top: 1px solid var(--capy-border-soft); }
.btn-mascot { display: flex; align-items: center; justify-content: center; gap: 6px; }
.btn-mascot-img { width: 18px; height: 18px; border-radius: 50%; object-fit: cover; }

.chat-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.chat-scroll {
  flex: 1; overflow-y: auto;
  padding: 24px 8px 12px;
  max-width: 860px; width: 100%; margin: 0 auto;
}

.chat-empty { text-align: center; padding-top: 8vh; }
.empty-scene { margin: 16px auto 10px; max-width: 340px; border-radius: 24px; overflow: hidden; box-shadow: 0 12px 36px var(--capy-primary-glow); opacity: .95; }
.empty-scene img { width: 100%; height: auto; display: block; }
.empty-logo { font-size: 64px; margin-bottom: 12px; }
.empty-logo img { width: 96px; height: 96px; object-fit: cover; border-radius: 28px; box-shadow: 0 8px 28px var(--capy-primary-glow); }
.empty-title { font-size: 22px; font-weight: 700; }
.empty-sub { color: var(--capy-text2); margin-top: 4px; }
.empty-hints { margin-top: 24px; display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }

.msg-row { display: flex; gap: 10px; margin-bottom: 18px; align-items: flex-start; }
.msg-row.user { flex-direction: row-reverse; }
.msg-avatar {
  width: 34px; height: 34px; flex: 0 0 auto;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  background: var(--capy-primary-soft);
  border: 1px solid var(--capy-primary-border);
  border-radius: var(--capy-radius-pill);
  overflow: hidden;
}
.avatar-img { width: 26px; height: 26px; object-fit: cover; border-radius: 50%; }
.msg-bubble {
  max-width: 76%;
  padding: 10px 14px;
  border-radius: var(--capy-radius-lg);
  white-space: pre-wrap;
  line-height: 1.65;
}
.msg-row.assistant .msg-bubble { background: var(--capy-bot-bg); border: 1px solid var(--capy-border-soft); border-top-left-radius: 4px; }
.msg-row.user .msg-bubble { background: var(--capy-user-bg); border: 1px solid var(--capy-primary-border); border-top-right-radius: 4px; }

.chat-input-row {
  flex: 0 0 auto;
  padding: 10px 16px 16px;
  max-width: 860px; width: 100%; margin: 0 auto;
}
.input-box {
  background: var(--capy-card);
  border: 1px solid var(--capy-primary-border);
  border-radius: var(--capy-radius-xl);
  padding: 10px 12px;
  box-shadow: var(--capy-shadow-card);
  transition: var(--capy-transition);
}
.input-box:focus-within { box-shadow: 0 0 0 3px var(--capy-primary-soft), var(--capy-shadow-card); }
.chat-textarea {
  width: 100%;
  background: transparent;
  border: none; outline: none; resize: none;
  min-height: 44px; max-height: 160px;
  color: var(--capy-text);
  font-size: 14px; line-height: 1.6;
  padding: 4px 6px;
}
.input-actions { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 4px 6px 0; }
.input-hint { font-size: 12px; color: var(--capy-text2); }
</style>
