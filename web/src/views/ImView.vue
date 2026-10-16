<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2><img class="head-icon" src="/capy/capy_gif07.gif" alt="IM" /> IM 通道</h2>
        <div class="sub">标准机器人 Webhook 与本地接收通道，微信 / QQ 个人号协议不做逆向接入</div>
      </div>
      <div class="head-actions">
        <button class="btn im-btn" @click="refresh" :disabled="busy">
          <img v-if="busy" class="btn-busy-img" src="/capy/capy_gif04.gif" alt="busy" /> 刷新
        </button>
        <button class="btn btn-primary im-btn" @click="startAdd">
          <img class="btn-ico-img" src="/capy/capy_gif01.gif" alt="新增" /> ＋ 新增通道
        </button>
      </div>
    </div>

    <!-- 操作反馈 -->
    <div v-if="msg" class="im-msg" :class="{ err: msgErr }">{{ msg }}</div>

    <!-- 通道卡片 -->
    <div class="capy-panel">
      <div class="panel-head">
        <span class="panel-title">通道配置 <span class="badge">{{ channels.length }}</span></span>
        <span class="panel-sub">webhook = 钉钉 / 企业微信群机器人；httpin = 本地接收（模拟 IM 推送）</span>
      </div>

      <!-- 新增 / 编辑表单 -->
      <div v-if="editing" class="im-form capy-form">
        <div class="form-row">
          <input v-model="form.name" class="input grow" placeholder="通道名称（如：运维群机器人）" />
          <select v-model="form.type" class="input type-sel">
            <option value="webhook">webhook（钉钉 / 企业微信机器人）</option>
            <option value="httpin">httpin（本地接收）</option>
          </select>
        </div>
        <div class="form-row">
          <input v-if="form.type === 'webhook'" v-model="form.webhook_url" class="input grow" placeholder="机器人 Webhook URL" />
          <span v-else class="form-hint">httpin 通道无需 Webhook URL，由噜噜本地接收</span>
          <label class="chk"><input type="checkbox" v-model="form.enabled" /> 启用</label>
          <button class="btn btn-primary" @click="submitForm" :disabled="busy">
            <img v-if="busy" class="btn-busy-img" src="/capy/capy_gif04.gif" alt="busy" /> {{ form.origin ? '保存修改' : '创建' }}
          </button>
          <button class="btn" @click="editing = false">取消</button>
        </div>
      </div>

      <div v-if="channels.length" class="channel-grid">
        <div v-for="c in channels" :key="c.name" class="channel-card">
          <div class="channel-head">
            <span class="channel-name">{{ c.name }}</span>
            <div class="channel-badges">
              <span class="badge badge-yellow">{{ c.type }}</span>
              <span class="badge" :class="c.enabled ? 'badge-ok' : 'badge-off'">{{ c.enabled ? '启用' : '停用' }}</span>
            </div>
          </div>
          <div class="channel-url" :title="c.webhook_url || '—'">{{ c.webhook_url ? shortUrl(c.webhook_url) : '—' }}</div>
          <div class="channel-foot">
            <button class="btn btn-mini" @click="startEdit(c)">编辑</button>
            <button class="btn btn-mini btn-primary" @click="sendTest(c)" :disabled="busy">
              <img v-if="busy" class="btn-busy-img" src="/capy/capy_gif04.gif" alt="busy" /> 发测试
            </button>
            <button class="btn btn-mini btn-danger" @click="delChannel(c)">删除</button>
          </div>
        </div>
      </div>
      <div v-else class="empty-tip">
        <img class="empty-img" src="/capy/capy_gif06.gif" alt="空状态" />
        <div>还没有通道，点「新增通道」加一个～</div>
      </div>
    </div>

    <!-- 模拟推送 -->
    <div class="capy-panel">
      <div class="panel-head">
        <span class="panel-title">模拟推送（外部接收端点）</span>
        <span class="panel-sub">POST /api/im/inbox/incoming 等效：选通道发一条，噜噜处理后经原通道回发</span>
      </div>
      <div class="im-form">
        <select v-model="pushChannel" class="input type-sel">
          <option v-for="c in channels" :key="c.name" :value="c.name">{{ c.name }}</option>
        </select>
        <input v-model="pushText" class="input grow" placeholder="要推送给噜噜的消息内容" @keyup.enter="pushIncoming" />
        <button class="btn btn-primary" @click="pushIncoming" :disabled="busy || !pushText.trim()">
          <img v-if="busy" class="btn-busy-img" src="/capy/capy_gif04.gif" alt="busy" /> 推送
        </button>
      </div>
    </div>

    <!-- 收件箱 -->
    <div class="capy-panel">
      <div class="panel-head">
        <span class="panel-title">收件箱 <span class="badge">{{ inbox.length }}</span></span>
        <span class="panel-sub">incoming 入站 · outgoing 回发；状态：pending / processed / sent / failed</span>
        <button class="btn btn-mini btn-danger" @click="clearInbox" :disabled="busy">清空</button>
      </div>
      <div v-if="inbox.length" class="inbox-list">
        <div v-for="m in inbox" :key="m.id" class="inbox-card">
          <div class="inbox-top">
            <span class="badge" :class="m.direction === 'incoming' ? 'badge-ok' : 'badge-off'">{{ m.direction }}</span>
            <span class="inbox-channel">{{ m.channel }}</span>
            <span class="badge" :class="statusCls(m.status)">{{ m.status }}</span>
            <span class="inbox-time">{{ m.created_at }}</span>
          </div>
          <div class="inbox-text" :title="m.text">{{ m.text }}</div>
          <div v-if="m.reply" class="inbox-reply" :title="m.reply">↩ {{ m.reply }}</div>
        </div>
      </div>
      <div v-else class="empty-tip">
        <img class="empty-img" src="/capy/capy_gif05.gif" alt="空状态" />
        <div>收件箱空空的，用「模拟推送」发一条试试。</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { imApi } from '../api'
import { toast } from '../composables/toast'

const channels = ref([])
const inbox = ref([])
const busy = ref(false)
const msg = ref('')
const msgErr = ref(false)
const editing = ref(false)
const form = ref({ origin: '', name: '', type: 'webhook', webhook_url: '', enabled: true })
const pushChannel = ref('')
const pushText = ref('')

function flash(text, isErr = false) {
  msg.value = text
  msgErr.value = isErr
  setTimeout(() => { msg.value = '' }, 5000)
}

function shortUrl(url) {
  try {
    const u = new URL(url)
    return u.host + u.pathname.slice(0, 30) + (u.pathname.length > 30 ? '…' : '')
  } catch (e) {
    return url.length > 48 ? url.slice(0, 48) + '…' : url
  }
}

function statusCls(s) {
  return s === 'processed' || s === 'sent' ? 'badge-ok' : (s === 'failed' ? 'badge-danger' : 'badge-yellow')
}

async function refresh() {
  try {
    const [cs, ib] = await Promise.all([imApi.channels(), imApi.inbox(100)])
    channels.value = cs.items || []
    if (!pushChannel.value && channels.value.length) pushChannel.value = channels.value[0].name
    inbox.value = ib.items || []
  } catch (e) {
    flash('加载失败：' + e.message, true)
  }
}

function startAdd() {
  editing.value = true
  form.value = { origin: '', name: '', type: 'webhook', webhook_url: '', enabled: true }
}

function startEdit(c) {
  editing.value = true
  form.value = { origin: c.name, name: c.name, type: c.type, webhook_url: c.webhook_url || '', enabled: !!c.enabled }
}

async function submitForm() {
  if (!form.value.name.trim()) { flash('通道名称不能为空', true); return }
  busy.value = true
  try {
    const body = { name: form.value.name.trim(), type: form.value.type, webhook_url: form.value.webhook_url.trim(), enabled: form.value.enabled }
    const r = form.value.origin
      ? await imApi.update(form.value.origin, body)
      : await imApi.add(body)
    flash(r.message || '已保存')
    editing.value = false
    await refresh()
  } catch (e) {
    flash('保存失败：' + e.message, true)
  } finally {
    busy.value = false
  }
}

async function delChannel(c) {
  try {
    const r = await imApi.del(c.name)
    flash(r.message || '已删除')
    if (pushChannel.value === c.name) pushChannel.value = ''
    await refresh()
  } catch (e) {
    flash('删除失败：' + e.message, true)
  }
}

async function sendTest(c) {
  busy.value = true
  try {
    const r = await imApi.test(c.name, 'capylulu 通道测试：噜噜在吗？')
    const res = r.result || {}
    flash(`${c.name}：${res.message || (res.ok ? '发送成功' : '发送失败')}`)
  } catch (e) {
    flash('发送测试失败：' + e.message, true)
  } finally {
    busy.value = false
  }
}

async function pushIncoming() {
  if (!pushChannel.value) { flash('请先选择通道', true); return }
  busy.value = true
  try {
    const r = await imApi.incoming(pushChannel.value, pushText.value.trim())
    pushText.value = ''
    flash(r.processed > 0 ? `已推送并处理 ${r.processed} 条，回复经「${pushChannel.value}」回发` : (r.failed > 0 ? '推送完成，但处理失败' : '已入队'))
    await refresh()
  } catch (e) {
    flash('推送失败：' + e.message, true)
  } finally {
    busy.value = false
  }
}

async function clearInbox() {
  try {
    const r = await imApi.clearInbox()
    flash(r.message || '已清空')
    await refresh()
  } catch (e) {
    flash('清空失败：' + e.message, true)
  }
}

onMounted(refresh)
</script>

<style scoped>
.head-icon { width: 22px; height: 22px; border-radius: 6px; object-fit: cover; vertical-align: -4px; margin-right: 6px; }
.btn-ico-img { width: 16px; height: 16px; border-radius: 4px; object-fit: cover; vertical-align: -3px; margin-right: 4px; }
.btn-busy-img { width: 16px; height: 16px; border-radius: 4px; object-fit: cover; vertical-align: -3px; margin-right: 4px; animation: spin-busy 1.2s linear infinite; }
@keyframes spin-busy { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.im-btn { display: inline-flex; align-items: center; }
.im-msg {
  margin-bottom: 12px; padding: 10px 14px;
  border-radius: var(--capy-radius-md);
  background: var(--capy-primary-soft);
  border: 1px solid var(--capy-primary-border);
  font-size: 13px;
}
.im-msg.err { background: var(--capy-danger-soft, rgba(239, 112, 96, .15)); color: var(--capy-danger, #ef7060); }

/* 通道卡片 */
.channel-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.channel-card {
  display: flex; flex-direction: column; gap: 10px;
  padding: 14px 16px;
  background: var(--capy-glass-card, rgba(255,255,255,.5));
  border: 1px solid var(--capy-border-soft);
  border-radius: var(--capy-radius-md);
  transition: var(--capy-transition);
}
.channel-card:hover { transform: translateY(-2px); box-shadow: var(--capy-shadow-hover); }
.channel-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.channel-name { font-weight: 700; font-size: 15px; }
.channel-badges { display: flex; gap: 6px; }
.channel-url { font-size: 12px; color: var(--capy-text2); word-break: break-all; min-height: 16px; }
.channel-foot { display: flex; gap: 6px; justify-content: flex-end; }
.btn-mini { padding: 2px 10px; font-size: 12px; display: inline-flex; align-items: center; gap: 2px; }

/* 表单 */
.im-form { display: grid; gap: 10px; margin-bottom: 14px; padding: 14px 16px; }
.form-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.type-sel { width: 220px; }
.chk { display: flex; align-items: center; gap: 4px; font-size: 13px; white-space: nowrap; }
.form-hint { font-size: 12px; color: var(--capy-text2); flex: 1; }
.grow { flex: 1; min-width: 160px; }

/* 收件箱卡片 */
.inbox-list { display: flex; flex-direction: column; gap: 10px; }
.inbox-card {
  padding: 12px 14px;
  background: var(--capy-glass-card, rgba(255,255,255,.45));
  border: 1px solid var(--capy-border-soft);
  border-radius: var(--capy-radius-md);
  transition: var(--capy-transition);
}
.inbox-card:hover { box-shadow: var(--capy-shadow-hover); }
.inbox-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; }
.inbox-channel { font-weight: 600; }
.inbox-time { color: var(--capy-text2); margin-left: auto; font-size: 12px; }
.inbox-text { margin-top: 8px; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.inbox-reply { margin-top: 4px; font-size: 12px; color: var(--capy-text2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.panel-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.panel-title { font-weight: 700; font-size: 14px; }
.panel-sub { font-size: 11px; color: var(--capy-text2); flex: 1; }
.empty-tip { color: var(--capy-text2); text-align: center; padding: 40px 0; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.empty-img { width: 96px; height: 96px; border-radius: 14px; object-fit: cover; opacity: .9; }
</style>
