<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2><img class="head-icon" src="/images/lulu/3.png" alt="任务" /> 自动任务</h2>
        <div class="sub">噜噜替你盯着点，到点就干活</div>
      </div>
      <div class="head-right">
        <span class="badge" :class="running ? 'badge-ok' : 'badge-off'">{{ running ? '调度器运行中' : '调度器已停止' }}</span>
        <button class="btn btn-outline" @click="toggleScheduler">
          <img v-if="running" class="btn-icon-img" src="/images/lulu/3.png" alt="停止" />
          <img v-else class="btn-icon-img" src="/images/lulu/5.png" alt="启动" />
          {{ running ? '停止' : '启动' }}
        </button>
      </div>
    </div>

    <div class="capy-panel add-panel">
      <div class="add-row">
        <button class="btn btn-primary" @click="openDialog">＋ 添加任务</button>
        <span class="add-hint">支持 提醒 / 便签 / 自动任务，web·win 自动任务可上传文件</span>
      </div>
    </div>

    <div class="capy-section table-card">
      <div v-for="(t, i) in tasks" :key="i" class="task-row">
        <label class="switch">
          <input type="checkbox" :checked="t.enabled" @change="toggleTask(t, $event)" />
          <span class="track"></span>
        </label>
        <div class="grow">
          <template v-if="isAuto(t)">
            <div class="task-text">
              {{ t.name }}
              <span v-if="runningBy(t.name)" class="badge badge-run">{{ runPhase(t.name) }}</span>
            </div>
            <div class="task-meta">
              cron：{{ t.cron }} · 下次 {{ t.next || '—' }} ·
              <template v-if="stepCount(t)">多步脚本 {{ stepCount(t) }} 步</template>
              <template v-else>{{ t.module }}.{{ t.func }}</template>
            </div>
          </template>
          <template v-else>
            <div class="task-text">{{ t.text }}</div>
            <div class="task-meta">{{ t.next || '' }}</div>
          </template>
        </div>
        <div class="row-ops">
          <button class="btn btn-ghost btn-sm" @click="isAuto(t) ? editTask(t) : editRemind(t)">编辑</button>
          <button class="btn btn-ghost btn-icon btn-sm" @click="removeTask(t)" title="删除"><img class="btn-icon-img" src="/images/lulu/7.png" alt="删除" /></button>
        </div>
      </div>
      <div v-if="!tasks.length" class="empty-tip">还没有自动任务，添加一个试试。</div>
    </div>

    <div class="page-head logs-head">
      <h3><img class="head-icon" src="/images/lulu/2.png" alt="日志" /> 执行日志</h3>
    </div>
    <div class="capy-section table-card log-card">
      <div v-for="(l, j) in logs" :key="j" class="log-row">
        <span class="log-time">{{ l.time || l.ts || '' }}</span>
        <span class="log-text">{{ l.text }}</span>
        <span v-if="l.result" class="log-result">{{ l.result }}</span>
      </div>
      <div v-if="!logs.length" class="empty-tip">暂无日志。</div>
    </div>

    <!-- 添加任务弹窗 -->
    <div v-if="showDialog" class="dialog-mask" @click.self="closeDialog">
      <div class="dialog">
        <div class="dialog-head">
          <h3>{{ editingName ? '编辑任务' : '添加任务' }}</h3>
          <button class="btn btn-ghost btn-icon btn-sm" @click="closeDialog" title="关闭">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-row">
            <label class="form-label">一句话创建</label>
            <div class="parse-row">
              <input v-model="naturalText" class="input" placeholder="例：每天早上9点打开钉钉并发送工作汇报" @keyup.enter="parseTask" />
              <button type="button" class="btn btn-outline btn-sm parse-btn" :disabled="parsing" @click="parseTask">{{ parsing ? '解析中…' : '智能解析' }}</button>
            </div>
          </div>
          <div v-if="parsedSteps.length" class="form-row">
            <label class="form-label">已识别流程</label>
            <div class="upload-list">
              <div v-for="(s, si) in parsedSteps" :key="si" class="upload-item">{{ si + 1 }}. {{ s.desc || (s.module + '.' + s.func) }}</div>
            </div>
          </div>
          <div class="form-row">
            <label class="form-label">动作类型</label>
            <div class="seg">
              <button type="button" :class="{ active: form.action === 'remind' }" @click="setAction('remind')">提醒</button>
              <button type="button" :class="{ active: form.action === 'note' }" @click="setAction('note')">便签</button>
              <button type="button" :class="{ active: form.action === 'auto' }" @click="setAction('auto')">自动任务</button>
            </div>
          </div>
          <div class="form-row">
            <label class="form-label">任务名称</label>
            <input v-model="form.name" class="input" :placeholder="form.action === 'auto' ? '自动任务名称（必填）' : '可选，仅自动任务必填'" />
          </div>
          <div class="form-row">
            <label class="form-label">内容描述</label>
            <input v-model="form.content" class="input" :placeholder="form.action === 'auto' ? '自动任务说明（可选）' : '例：喝水、写周报（必填）'" />
          </div>
          <div class="form-row">
            <label class="form-label">时间</label>
            <input v-model="form.time" type="time" class="input time-input" />
          </div>
          <div class="form-row">
            <label class="form-label">执行周期</label>
            <div class="seg">
              <button type="button" :class="{ active: form.period === 'daily' }" @click="form.period = 'daily'">每天</button>
              <button type="button" :class="{ active: form.period === 'weekly' }" @click="form.period = 'weekly'">每周</button>
              <button type="button" :class="{ active: form.period === 'once' }" @click="form.period = 'once'">一次性</button>
              <button v-if="form.action === 'auto'" type="button" :class="{ active: form.period === 'custom' }" @click="form.period = 'custom'">自定义cron</button>
            </div>
          </div>
          <div v-if="form.period === 'weekly'" class="form-row">
            <label class="form-label">每周</label>
            <div class="weekdays">
              <button v-for="(w, wi) in weekNames" :key="wi" type="button" :class="{ active: form.weekdays.includes(wi) }" @click="toggleWeekday(wi)">{{ w }}</button>
            </div>
          </div>
          <div v-if="form.period === 'custom'" class="form-row">
            <label class="form-label">cron 表达式</label>
            <input v-model="form.cronExpr" class="input" placeholder="分 时 日 月 周，如：30 9 * * 1-5" />
          </div>

          <template v-if="form.action === 'auto'">
            <div class="form-row">
              <label class="form-label">执行后通知</label>
              <label class="switch-label"><input type="checkbox" v-model="form.notify" /> 任务执行后弹窗通知</label>
            </div>
            <div class="form-row">
              <label class="form-label">分类</label>
              <select v-model="autoGroup" class="input" @change="onGroupChange">
                <option value="web">web（浏览器）</option>
                <option value="win">win（桌面）</option>
                <option value="other">other（其他）</option>
              </select>
            </div>
            <div class="form-row">
              <label class="form-label">函数</label>
              <select v-model="autoFuncKey" class="input">
                <option v-for="f in autoGroups[autoGroup]" :key="f.full" :value="f.full">{{ f.func }} — {{ f.module }}</option>
              </select>
            </div>
            <div v-if="autoGroup === 'web' || autoGroup === 'win'" class="form-row">
              <label class="form-label">上传文件</label>
              <input type="file" class="input file-input" :disabled="uploading" @change="uploadFile" />
            </div>
            <div v-if="uploads.length" class="form-row">
              <label class="form-label">已上传</label>
              <div class="upload-list">
                <div v-for="(u, ui) in uploads" :key="ui" class="upload-item">{{ u.name }} → {{ u.path }}</div>
              </div>
            </div>
            <div class="form-row">
              <label class="form-label">参数</label>
              <div class="param-list">
                <div v-for="(p, pi) in params" :key="pi" class="param-row">
                  <input v-model="p.key" class="input param-key" placeholder="参数名" />
                  <input v-model="p.value" class="input param-val" placeholder="参数值" />
                  <button type="button" class="btn btn-ghost btn-icon btn-sm" @click="removeParam(pi)" title="删除参数">×</button>
                </div>
                <button type="button" class="btn btn-outline btn-sm" @click="addParam">＋ 添加参数</button>
              </div>
            </div>
          </template>
        </div>
        <div class="dialog-foot">
          <button class="btn btn-outline" @click="closeDialog">取消</button>
          <button class="btn btn-primary" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : (editingName ? '确认保存' : '确认添加') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { tasksApi, miscApi } from '../api'
import { toast } from '../composables/toast'

const tasks = ref([])
const logs = ref([])
const running = ref(false)
const runningTasks = ref([])  // 当前正在执行的自动任务（后端轮询）
let runningTimer = null
let logTimer = null
const showDialog = ref(false)
const submitting = ref(false)
const editingName = ref('')  // 非空=编辑模式，值为原任务名（编辑时锁定名称）
const weekNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const form = reactive({
  name: '',
  content: '',
  time: '09:00',
  period: 'daily',   // daily / weekly / once / custom
  weekdays: [0],     // 0=周一 .. 6=周日
  cronExpr: '',
  action: 'remind',  // remind / note / auto
  notify: false,        // 自动任务执行后是否弹窗通知（默认不弹）
})
const autoGroups = ref({ web: [], win: [], other: [] })
const autoGroup = ref('web')
const autoFuncKey = ref('')
const params = ref([])
const uploads = ref([])
const uploading = ref(false)
const naturalText = ref('')  // 一句话创建输入
const parsing = ref(false)   // 智能解析中
const editingSteps = ref([]) // 编辑/解析出的多步脚本（steps 任务专用）
const parsedSteps = ref([])  // 一句话解析出的流程预览

async function load() {
  try {
    const r = await tasksApi.list()
    tasks.value = r.items || []
  } catch (e) { toast('任务加载失败：' + e.message) }
  try {
    const l = await tasksApi.logs()
    logs.value = (l.items || []).slice(0, 50)
  } catch (e) { /* ignore */ }
}

function isAuto(t) {
  return !!(t && ((t.module && t.func) || (Array.isArray(t.steps) && t.steps.length) || (t.mode === 'agentic' && (t.goal || '').trim())))
}
function stepCount(t) {
  return Array.isArray(t.steps) ? t.steps.length : 0
}

// ---- 弹窗 ----

function openDialog() {
  editingName.value = ''
  editingSteps.value = []
  parsedSteps.value = []
  Object.assign(form, {
    name: '', content: '', time: '09:00',
    period: 'daily', weekdays: [0], cronExpr: '', action: 'remind', notify: false,
  })
  autoGroup.value = 'web'
  autoFuncKey.value = autoGroups.value.web?.[0]?.full || ''
  params.value = []
  uploads.value = []
  naturalText.value = ''
  parsing.value = false
  showDialog.value = true
}

// 编辑入口：复用添加弹窗，预填原任务字段，只改需要改的
function editRemind(t) {
  editingName.value = t.text || ''
  Object.assign(form, {
    name: '',
    content: extractContent(t),
    time: t.time || '09:00',
    period: kindToPeriod(t.kind),
    weekdays: t.weekday != null && t.weekday >= 0 && t.weekday <= 6 ? [t.weekday] : [0],
    cronExpr: '',
    action: t.action === 'note' ? 'note' : 'remind',
    notify: false,
  })
  params.value = []
  uploads.value = []
  showDialog.value = true
}

// 从任务文本反解析出内容主体：去周期前缀/时间/动作词
function extractContent(t) {
  let s = t.text || ''
  s = s.replace(/^(每天|每日|每周(星期|周)?[一二三四五六日天1-7]|今天|明天|一次性)\s*/i, '')
  s = s.replace(/^\s*\d{1,2}\s*[:：]\s*\d{1,2}\s*/, '')
  s = s.replace(/^\s*\d{1,2}\s*点(半)?\s*/, '')
  s = s.replace(/^(提醒|通知|叫我|喊我|便签|备注|备忘|记下|记录)\s*/, '')
  return s.trim()
}

function kindToPeriod(kind) {
  if (kind === 'weekly') return 'weekly'
  if (kind === 'once') return 'once'
  return 'daily'
}

function editTask(t) {
  editingName.value = t.name || ''
  editingSteps.value = Array.isArray(t.steps) ? t.steps : []
  if (editingSteps.value.length) {
    // 多步任务：仅编辑调度与描述，脚本步骤原样保留
    Object.assign(form, {
      name: t.name || '',
      content: t.desc || '',
      action: 'auto',
      notify: !!t.notify,
    })
    fillCron(t.cron || '')
    params.value = []
    uploads.value = []
    showDialog.value = true
    return
  }
  autoGroup.value = groupOfFunc(t.module || '')
  if (autoGroups.value[autoGroup.value]?.some(x => x.full === `${t.module}.${t.func}`)) {
    autoFuncKey.value = `${t.module}.${t.func}`
  } else {
    autoFuncKey.value = ''
  }
  Object.assign(form, {
    name: t.name || '',
    content: t.desc || '',
    action: 'auto',
    notify: !!t.notify,
  })
  fillCron(t.cron || '')
  params.value = Object.entries(t.params || {}).map(([k, v]) => ({ key: k, value: String(v) }))
  // 原 params 里若带 file，展示为已上传，便于用户识别
  uploads.value = Object.entries(t.params || {})
    .filter(([k]) => k === 'file')
    .map(([k, v]) => ({ name: '原附件（file 参数）', path: String(v) }))
  showDialog.value = true
}

function groupOfFunc(module) {
  const m = (module || '').split('.').pop()
  if (m === 'browser_ops') return 'web'
  if (['desktop', 'window_ops', 'process_ops', 'input_ops', 'gui_ops'].includes(m)) return 'win'
  return 'other'
}

// 五段 cron → 表单周期字段
function fillCron(cron) {
  const parts = String(cron || '').trim().split(/\s+/)
  if (parts.length !== 5) { form.period = 'custom'; form.cronExpr = cron || ''; return }
  const [mm, hh, dd, mon, dow] = parts
  form.time = `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
  // 一次性（固定日期）等其余情况兜底为自定义 cron
  if (dd !== '*' || mon !== '*') { form.period = 'custom'; form.cronExpr = cron || ''; return }
  if (dow === '*') {
    form.period = 'daily'
  } else {
    const dows = dow.split(',')
    // cron 星期：0/7=周日, 1=周一..6=周六 → 前端 0=周一..6=周日
    const wds = dows.map(d => (d === '0' || d === '7' ? 6 : Number(d) - 1)).filter(d => d >= 0 && d <= 6)
    if (wds.length) { form.period = 'weekly'; form.weekdays = [...new Set(wds)].sort((a, b) => a - b) }
    else { form.period = 'custom'; form.cronExpr = cron || '' }
  }
}

function closeDialog() {
  if (submitting.value) return
  showDialog.value = false
}

async function loadOptions() {
  try {
    const r = await tasksApi.autoOptions()
    autoGroups.value = r.groups || { web: [], win: [], other: [] }
    if (!autoFuncKey.value) {
      const first = autoGroups.value[autoGroup.value]?.[0]
      autoFuncKey.value = first?.full || ''
    }
  } catch (e) { toast('自动任务选项加载失败：' + e.message) }
}

function setAction(a) {
  form.action = a
  if (a !== 'auto' && form.period === 'custom') form.period = 'daily'
}

function onGroupChange() {
  autoFuncKey.value = autoGroups.value[autoGroup.value]?.[0]?.full || ''
}

// 一句话创建：自然语言 → 自动预填表单（单步：函数/参数；多步：完整脚本），用户只需确认
async function parseTask() {
  const text = naturalText.value.trim()
  if (!text) { toast('请先输入一句话任务描述'); return }
  parsing.value = true
  try {
    const r = await tasksApi.parse(text)
    if (!r.ok) { toast(r.error || '智能解析失败'); return }
    form.action = 'auto'
    form.name = r.name || ''
    form.content = r.note || text
    if (r.cron) fillCron(r.cron)
    if (Array.isArray(r.steps) && r.steps.length) {
      // 多步完整流程：直接交给 steps 提交
      editingSteps.value = r.steps
      parsedSteps.value = r.steps
      params.value = []
      uploads.value = []
      toast(`解析成功，已识别 ${r.steps.length} 步完整流程，确认无误后点“确认添加”`)
    } else {
      editingSteps.value = []
      parsedSteps.value = []
      const g = groupOfFunc(r.module || '')
      autoGroup.value = g
      autoFuncKey.value = autoGroups.value[g]?.some(x => x.full === `${r.module}.${r.func}`)
        ? `${r.module}.${r.func}` : (autoGroups.value[g]?.[0]?.full || '')
      params.value = Object.entries(r.params || {}).map(([k, v]) => ({ key: k, value: String(v) }))
      toast('解析成功，已自动填写函数和参数，确认无误后点“确认添加”')
    }
  } catch (e) { toast('智能解析失败：' + e.message) }
  finally { parsing.value = false }
}

function toggleWeekday(i) {
  const idx = form.weekdays.indexOf(i)
  if (idx >= 0) form.weekdays.splice(idx, 1)
  else form.weekdays.push(i)
}

function addParam() { params.value.push({ key: '', value: '' }) }
function removeParam(i) { params.value.splice(i, 1) }

function collectParams() {
  const obj = {}
  for (const p of params.value) {
    if (p.key.trim()) obj[p.key.trim()] = p.value
  }
  return obj
}

function selectedFunc() {
  const key = autoFuncKey.value
  for (const list of Object.values(autoGroups.value)) {
    const f = list.find(x => x.full === key)
    if (f) return f
  }
  return null
}

// 时间(HH:MM) + 周期 → 五段 cron（分 时 日 月 周）
function buildCron() {
  const t = form.time || ''
  if (!/^\d{1,2}:\d{2}$/.test(t)) { toast('请填写正确的时间（HH:MM）'); return '' }
  const [hh, mm] = t.split(':').map(Number)
  if (hh > 23 || mm > 59) { toast('时间超出范围'); return '' }
  const m = String(mm).padStart(2, '0')
  const h = String(hh).padStart(2, '0')
  if (form.period === 'daily') return `${m} ${h} * * *`
  if (form.period === 'weekly') {
    if (!form.weekdays.length) { toast('请至少选择一个周几'); return '' }
    // 前端 0=周一..6=周日 → cron 0/7=周日, 1=周一..6=周六
    const dows = form.weekdays.map(w => (w === 6 ? 0 : w + 1)).sort((a, b) => a - b).join(',')
    return `${m} ${h} * * ${dows}`
  }
  if (form.period === 'once') {
    const d = new Date()
    return `${m} ${h} ${d.getDate()} ${d.getMonth() + 1} *`
  }
  if (form.period === 'custom') {
    const cron = form.cronExpr.trim()
    if (!cron) { toast('请填写 cron 表达式'); return '' }
    return cron
  }
  return ''
}

// 提醒/便签 → 拼 "每天 HH:MM 提醒 内容" 文本
function remindTexts() {
  const action = form.action === 'note' ? '便签' : '提醒'
  const content = form.content.trim()
  if (!content) { toast('请填写内容描述'); return null }
  const t = form.time || ''
  if (!/^\d{1,2}:\d{2}$/.test(t)) { toast('请填写正确的时间（HH:MM）'); return null }
  const base = `${t} ${action} ${content}`
  if (form.period === 'daily') return [`每天 ${base}`]
  if (form.period === 'weekly') {
    if (!form.weekdays.length) { toast('请至少选择一个周几'); return null }
    return form.weekdays.map(w => `每周${weekNames[w]} ${base}`)
  }
  if (form.period === 'once') return [`今天 ${base}`]
  toast('提醒/便签仅支持 每天/每周/一次性 周期'); return null
}

async function submit() {
  if (submitting.value) return
  if (form.action === 'auto') {
    const name = form.name.trim()
    if (!name) { toast('请填写任务名称'); return }
    const cron = buildCron()
    if (!cron) return
    if (!editingSteps.value.length) {
      const f = selectedFunc()
      if (!f) { toast('请选择自动任务函数'); return }
    }
    submitting.value = true
    try {
      // 多步任务提交 steps；单步任务提交 module/func/params
      const body = { name: editingName.value || name, cron, notify: form.notify, desc: form.content }
      if (editingSteps.value.length) {
        body.steps = editingSteps.value
      } else {
        const f = selectedFunc()
        body.module = f.module
        body.func = f.func
        body.params = collectParams()
      }
      const r = await tasksApi.autoAdd(body)
      toast(r.message || (editingName.value ? '自动任务已更新' : '自动任务已添加'))
      closeDialog()
      await load()
    } catch (e) { toast((editingName.value ? '保存失败：' : '添加失败：') + e.message) }
    finally { submitting.value = false }
    return
  }
  const texts = remindTexts()
  if (!texts) return
  submitting.value = true
  try {
    if (editingName.value) {
      // 编辑提醒/便签：第一条替换原任务，剩余文本（如每周多天）按新增处理
      await tasksApi.update(editingName.value, texts[0])
      let extra = 0
      for (let i = 1; i < texts.length; i++) { await tasksApi.add(texts[i]); extra++ }
      toast(extra ? `任务已更新，另新增 ${extra} 条` : '任务已更新')
    } else {
      for (const t of texts) {
        const r = await tasksApi.add(t)
        toast(r.message || '任务已添加')
      }
    }
    closeDialog()
    await load()
  } catch (e) { toast((editingName.value ? '保存失败：' : '添加失败：') + e.message) }
  finally { submitting.value = false }
}

// ---- 上传文件 ----

async function uploadFile(ev) {
  const file = ev.target.files && ev.target.files[0]
  if (!file) return
  uploading.value = true
  try {
    const r = await tasksApi.upload(file)
    uploads.value.push({ name: file.name, path: r.path })
    params.value.push({ key: 'file', value: r.path })
    toast('已上传：' + file.name)
  } catch (e) { toast('上传失败：' + e.message) }
  finally { uploading.value = false; ev.target.value = '' }
}

// ---- 列表操作 ----

async function toggleTask(t, ev) {
  const checked = ev.target.checked
  try {
    const r = isAuto(t) ? await tasksApi.autoToggle(t.name, checked) : await tasksApi.toggle(t.text, checked)
    toast(r.message || (checked ? '已启用' : '已停用'))
    await load()
  } catch (e) {
    ev.target.checked = !checked
    toast('操作失败：' + e.message)
  }
}

async function removeTask(t) {
  const label = isAuto(t) ? t.name : t.text
  if (!window.confirm(`确定删除任务「${label}」？`)) return
  try {
    const r = isAuto(t) ? await tasksApi.autoDel(t.name) : await tasksApi.del(t.text)
    toast(r.message || '已删除')
    await load()
  } catch (e) { toast('删除失败：' + e.message) }
}

async function toggleScheduler() {
  try {
    const r = running.value ? await miscApi.schedulerStop() : await miscApi.schedulerStart()
    toast(r.message || '已切换')
    await refreshStatus()
  } catch (e) { toast('操作失败：' + e.message) }
}

async function refreshStatus() {
  try {
    const s = await miscApi.status()
    running.value = s.scheduler_running
  } catch (e) { /* ignore */ }
}

// ---- 运行中状态轮询：任务执行期间展示“正在运行 / 第N步”标记，日志自动刷新 ----

function runningBy(name) {
  return runningTasks.value.find((r) => r.name === name)
}

function runPhase(r) {
  return r && r.phase ? '运行中：' + r.phase : '运行中'
}

async function refreshRunning() {
  try {
    const s = await tasksApi.autoStatus()
    runningTasks.value = s.running || []
    // 有任务运行中 → 每轮顺带刷新日志，避免“刷新日志才知道结果”
    if (runningTasks.value.length && !logTimer) {
      await load()
    }
  } catch (e) { /* ignore */ }
}

onMounted(async () => {
  await load()
  await refreshStatus()
  loadOptions()
  runningTimer = setInterval(refreshRunning, 2500)
})

onBeforeUnmount(() => {
  if (runningTimer) clearInterval(runningTimer)
  if (logTimer) clearInterval(logTimer)
})
</script>

<style scoped>
.page { padding: 20px 24px; }
.head-icon { width: 22px; height: 22px; border-radius: 6px; object-fit: cover; vertical-align: -4px; margin-right: 6px; }
.btn-icon-img { width: 16px; height: 16px; border-radius: 4px; object-fit: cover; vertical-align: -3px; margin-right: 4px; }
.head-right { display: flex; align-items: center; gap: 10px; }
.add-panel { margin-bottom: 16px; padding: 16px 18px; }
.add-row { display: flex; align-items: center; gap: 10px; }
.add-hint { font-size: 12px; color: var(--capy-text2); }
.table-card { margin-bottom: 20px; }
.task-row { display: flex; align-items: center; gap: 12px; padding: 10px 4px; border-bottom: 1px solid var(--capy-border-soft); }
.task-row:last-child { border-bottom: none; }
.grow { flex: 1; min-width: 0; }
.row-ops { display: flex; align-items: center; gap: 8px; }
.task-text { font-size: 14px; }
.task-meta { font-size: 12px; color: var(--capy-text2); margin-top: 2px; }
.logs-head { margin-bottom: 8px; }
.log-card { max-height: 380px; overflow-y: auto; }
.log-row { display: flex; gap: 10px; padding: 6px 0; font-size: 13px; border-bottom: 1px dashed var(--capy-border-soft); align-items: baseline; }
.log-time { color: var(--capy-text2); flex: 0 0 auto; font-size: 12px; }
.log-text { flex: 1; }
.log-result { color: var(--capy-text2); font-size: 12px; }
.empty-tip { color: var(--capy-text2); text-align: center; padding: 24px 0; }

/* 弹窗 */
.dialog-mask { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.45); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: var(--capy-card); border: 1px solid var(--capy-border); border-radius: 12px; width: 580px; max-width: calc(100vw - 40px); max-height: calc(100vh - 60px); display: flex; flex-direction: column; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2); }
.dialog-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--capy-border-soft); }
.dialog-body { padding: 14px 18px; overflow-y: auto; }
.dialog-foot { display: flex; justify-content: flex-end; gap: 10px; padding: 12px 18px; border-top: 1px solid var(--capy-border-soft); }
.form-row { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.form-label { flex: 0 0 76px; font-size: 13px; color: var(--capy-text2); line-height: 30px; }
.seg { display: flex; gap: 8px; flex-wrap: wrap; }
.seg button { padding: 5px 14px; border: 1px solid var(--capy-border); border-radius: 6px; background: transparent; cursor: pointer; font-size: 13px; color: inherit; }
.seg button.active { background: var(--capy-primary); color: #fff; border-color: var(--capy-primary); }
.weekdays { display: flex; gap: 6px; flex-wrap: wrap; }
.weekdays button { width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--capy-border); background: transparent; cursor: pointer; font-size: 12px; color: inherit; }
.weekdays button.active { background: var(--capy-primary); color: #fff; border-color: var(--capy-primary); }
.time-input { width: 140px; }
.file-input { padding: 4px 6px; }
.upload-list { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--capy-text2); }
.upload-item { word-break: break-all; }
.param-list { flex: 1; min-width: 0; }
.param-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }
.param-key { width: 150px; }
.param-val { flex: 1; min-width: 0; }
.parse-row { flex: 1; min-width: 0; display: flex; gap: 8px; align-items: center; }
.parse-row .input { flex: 1; min-width: 0; }
.parse-btn { flex-shrink: 0; }
.parse-tip { font-size: 12px; color: var(--capy-text2); margin-top: 4px; }
</style>
