<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2><img class="head-icon" src="/lulu/3.png" alt="任务" /> 自动任务</h2>
        <div class="sub">噜噜替你盯着点，到点就干活</div>
      </div>
      <div class="head-right">
        <span class="badge" :class="running ? 'badge-ok' : 'badge-off'">{{ running ? '调度器运行中' : '调度器已停止' }}</span>
        <button class="btn btn-outline" @click="toggleScheduler">
          <img v-if="running" class="btn-icon-img" src="/lulu/3.png" alt="停止" />
          <img v-else class="btn-icon-img" src="/lulu/5.png" alt="启动" />
          {{ running ? '停止' : '启动' }}
        </button>
      </div>
    </div>

    <div class="capy-panel add-panel">
      <div class="add-row">
        <input v-model="draft" class="input" placeholder="例：每天早上 9 点提醒我喝水；每周五 18 点写周报" @keydown.enter="addTask" />
        <button class="btn btn-primary" @click="addTask">添加任务</button>
      </div>
    </div>

    <div class="capy-section table-card">
      <div v-for="t in tasks" :key="t.text" class="task-row">
        <label class="switch">
          <input type="checkbox" :checked="t.enabled" @change="toggleTask(t, $event)" />
          <span class="track"></span>
        </label>
        <div class="grow">
          <div class="task-text">{{ t.text }}</div>
          <div class="task-meta">{{ t.next || t.describe || '' }}</div>
        </div>
        <button class="btn btn-ghost btn-icon btn-sm" @click="removeTask(t)" title="删除"><img class="btn-icon-img" src="/lulu/7.png" alt="删除" /></button>
      </div>
      <div v-if="!tasks.length" class="empty-tip">还没有自动任务，添加一个试试。</div>
    </div>

    <div class="page-head logs-head">
      <h3><img class="head-icon" src="/lulu/2.png" alt="日志" /> 执行日志</h3>
    </div>
    <div class="capy-section table-card log-card">
      <div v-for="(l, i) in logs" :key="i" class="log-row">
        <span class="log-time">{{ l.time || l.ts || '' }}</span>
        <span class="log-text">{{ l.text }}</span>
        <span v-if="l.result" class="log-result">{{ l.result }}</span>
      </div>
      <div v-if="!logs.length" class="empty-tip">暂无日志。</div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { tasksApi, miscApi } from '../api'
import { toast } from '../composables/toast'

const tasks = ref([])
const logs = ref([])
const running = ref(false)
const draft = ref('')

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

async function addTask() {
  const text = draft.value.trim()
  if (!text) return
  try {
    const r = await tasksApi.add(text)
    toast(r.message || '任务已添加')
    draft.value = ''
    await load()
  } catch (e) { toast('添加失败：' + e.message) }
}

async function toggleTask(t, ev) {
  try {
    const r = await tasksApi.toggle(t.text, ev.target.checked)
    toast(r.message || (ev.target.checked ? '已启用' : '已停用'))
    await load()
  } catch (e) {
    ev.target.checked = !ev.target.checked
    toast('操作失败：' + e.message)
  }
}

async function removeTask(t) {
  if (!window.confirm(`确定删除任务「${t.text}」？`)) return
  try {
    const r = await tasksApi.del(t.text)
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

onMounted(async () => { await load(); await refreshStatus() })
</script>

<style scoped>
.page { padding: 20px 24px; }
.head-icon { width: 22px; height: 22px; border-radius: 6px; object-fit: cover; vertical-align: -4px; margin-right: 6px; }
.btn-icon-img { width: 16px; height: 16px; border-radius: 4px; object-fit: cover; vertical-align: -3px; margin-right: 4px; }
.head-right { display: flex; align-items: center; gap: 10px; }
.add-panel { margin-bottom: 16px; padding: 16px 18px; }
.add-row { display: flex; gap: 10px; }
.table-card { margin-bottom: 20px; }
.task-row { display: flex; align-items: center; gap: 12px; padding: 10px 4px; border-bottom: 1px solid var(--capy-border-soft); }
.task-row:last-child { border-bottom: none; }
.grow { flex: 1; min-width: 0; }
.task-text { font-size: 14px; }
.task-meta { font-size: 12px; color: var(--capy-text2); margin-top: 2px; }
.logs-head { margin-bottom: 8px; }
.log-card { max-height: 380px; overflow-y: auto; }
.log-row { display: flex; gap: 10px; padding: 6px 0; font-size: 13px; border-bottom: 1px dashed var(--capy-border-soft); align-items: baseline; }
.log-time { color: var(--capy-text2); flex: 0 0 auto; font-size: 12px; }
.log-text { flex: 1; }
.log-result { color: var(--capy-text2); font-size: 12px; }
.empty-tip { color: var(--capy-text2); text-align: center; padding: 24px 0; }
</style>
