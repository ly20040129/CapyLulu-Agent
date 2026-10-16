<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2><img class="head-icon" src="/lulu/6.png" alt="记忆" /> 用户记忆</h2>
        <div class="sub">噜噜记得住的东西，都在这里</div>
      </div>
      <div class="head-actions">
        <button class="btn" :class="{ active: showTiers }" @click="toggleTiers">
          {{ showTiers ? '单层记忆' : '三级记忆' }}
        </button>
        <button v-if="showTiers" class="btn btn-primary" @click="runDeepDream" :disabled="dreaming">
          {{ dreaming ? '蒸馏中…' : '深度蒸馏' }}
        </button>
        <button v-else class="btn btn-primary" @click="startCreate">＋ 新建记忆</button>
      </div>
    </div>

    <!-- 单层记忆（原有） -->
    <div v-if="!showTiers" class="memory-body">
      <aside class="mem-list">
        <div
          v-for="m in memories" :key="m.name"
          class="row-line" :class="{ active: m.name === currentName }"
          @click="openMemory(m.name)"
        >
          <img class="mem-icon" src="/lulu/6.png" alt="记忆" />
          <span class="grow mem-name">{{ m.name }}</span>
          <span class="badge">{{ m.size || '' }}</span>
        </div>
        <div v-if="!memories.length" class="empty-tip">暂无记忆。</div>
      </aside>

      <section class="mem-editor">
        <div v-if="!currentName && !creating" class="detail-empty">
          <div class="empty-logo"><img src="/lulu/6.png" alt="记忆" /></div>
          <div class="detail-scene"><img src="/lulu/scenes/study.png" alt="噜噜看书" /></div>
          <div class="empty-title">选一条记忆看看</div>
          <div class="empty-sub">噜噜靠这些记住你的偏好与知识</div>
        </div>
        <div v-else class="capy-panel editor-panel">
          <div class="field">
            <label>名称</label>
            <input v-model="editorName" class="input" :disabled="!creating" placeholder="如：我的常用文件夹" />
          </div>
          <div class="field">
            <label>内容</label>
            <textarea v-model="content" class="input" rows="14" placeholder="记点什么…"></textarea>
          </div>
          <div class="detail-actions">
            <button class="btn btn-secondary" @click="cancelEdit">取消</button>
            <button class="btn btn-primary" @click="save">保存</button>
            <button v-if="!creating" class="btn btn-danger" @click="remove">删除</button>
          </div>
        </div>
      </section>
    </div>

    <!-- 三级记忆（批次4） -->
    <div v-else class="memory-body">
      <aside class="tier-side">
        <div class="tier-search">
          <input v-model="queryKw" class="input" placeholder="合并检索：如 文件、会议、预算…" @keyup.enter="runQuery" />
          <button class="btn btn-primary" @click="runQuery">检索</button>
        </div>
        <div v-if="dreamMsg" class="dream-msg">{{ dreamMsg }}</div>
        <div v-if="dreamState" class="dream-state">
          上次蒸馏：{{ dreamState.last_time || '从未' }} ·
          情景 {{ dreamState.episodic_count }} · 语义 {{ dreamState.semantic_count }} ·
          工作 {{ dreamState.working_count }}
        </div>
        <div v-if="queryResults.length" class="query-results">
          <div class="tier-title">检索结果（语义>情景>工作）</div>
          <div v-for="(r, i) in queryResults" :key="i" class="qr-item">
            <span class="badge tier-badge" :class="'tier-' + r.tier">{{ tierLabel(r.tier) }}</span>
            <div class="qr-title">{{ r.title }}</div>
            <div class="qr-snippet">{{ r.snippet }}</div>
            <div class="qr-meta">相关度 {{ r.score }} · {{ r.time }}</div>
          </div>
          <div v-if="!queryResults.length" class="empty-tip">输入关键词试试。</div>
        </div>
      </aside>

      <section class="tier-main">
        <div v-for="t in tierKeys" :key="t" class="capy-panel tier-panel">
          <div class="tier-head">
            <span class="tier-dot" :class="'tier-' + t"></span>
            <span class="tier-name">{{ tierTitle(t) }}</span>
            <span class="badge">{{ tiers[t].length }}</span>
          </div>
          <div v-if="!tiers[t].length" class="empty-tip">暂无{{ tierTitle(t) }}条目。</div>
          <div v-for="it in tiers[t]" :key="it.id" class="tier-item">
            <div class="tier-item-title">{{ itemTitle(t, it) }}</div>
            <div class="tier-item-time">{{ itemTime(t, it) }}</div>
            <div class="tier-item-body">{{ itemBody(t, it) }}</div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { memoryApi } from '../api'
import { toast } from '../composables/toast'

const memories = ref([])
const currentName = ref('')
const editorName = ref('')
const content = ref('')
const creating = ref(false)

// 三级记忆（批次4）
const showTiers = ref(false)
const tiers = ref({ working: [], episodic: [], semantic: [] })
const tierKeys = ['working', 'episodic', 'semantic']
const queryKw = ref('')
const queryResults = ref([])
const dreamMsg = ref('')
const dreamState = ref(null)
const dreaming = ref(false)

const TIER_TITLE = { working: '工作记忆', episodic: '情景记忆', semantic: '语义记忆' }
function tierTitle(t) { return TIER_TITLE[t] || t }
function tierLabel(t) { return TIER_TITLE[t] || t }

async function load() {
  try {
    const r = await memoryApi.list()
    memories.value = r.items || []
  } catch (e) { toast('加载失败：' + e.message) }
}

async function openMemory(name) {
  creating.value = false
  currentName.value = name
  try {
    const r = await memoryApi.read(name)
    editorName.value = r.name
    content.value = r.content || ''
  } catch (e) { toast('读取失败：' + e.message) }
}

function startCreate() {
  creating.value = true
  currentName.value = ''
  editorName.value = ''
  content.value = ''
}

function cancelEdit() {
  if (creating.value) { creating.value = false; return }
  if (currentName.value) openMemory(currentName.value)
}

async function save() {
  if (!editorName.value.trim()) { toast('名称不能为空'); return }
  try {
    if (creating.value) {
      const r = await memoryApi.create(editorName.value.trim(), content.value)
      toast(r.message || '已创建')
      creating.value = false
    } else {
      const r = await memoryApi.save(currentName.value, content.value)
      toast(r.message || '已保存')
    }
    await load()
  } catch (e) { toast('保存失败：' + e.message) }
}

async function remove() {
  if (!window.confirm(`确定删除记忆「${currentName.value}」？`)) return
  try {
    const r = await memoryApi.del(currentName.value)
    toast(r.message || '已删除')
    currentName.value = ''
    content.value = ''
    await load()
  } catch (e) { toast('删除失败：' + e.message) }
}

// ---------------- 三级记忆 ----------------

function toggleTiers() {
  showTiers.value = !showTiers.value
  if (showTiers.value) loadTiers()
}

async function loadTiers() {
  try {
    const r = await memoryApi.tiers()
    tiers.value = {
      working: r.working || [],
      episodic: r.episodic || [],
      semantic: r.semantic || [],
    }
    const d = await memoryApi.lastDream()
    dreamState.value = d || null
  } catch (e) { toast('三级记忆加载失败：' + e.message) }
}

async function runDeepDream() {
  dreaming.value = true
  dreamMsg.value = ''
  try {
    const r = await memoryApi.deepDream(true, 50)
    dreamMsg.value = r.message || '蒸馏完成'
    toast(dreamMsg.value)
    await loadTiers()
  } catch (e) { toast('蒸馏失败：' + e.message) } finally {
    dreaming.value = false
  }
}

async function runQuery() {
  const q = queryKw.value.trim()
  if (!q) { toast('请输入关键词'); return }
  try {
    const r = await memoryApi.query(q, 10)
    queryResults.value = r.items || []
  } catch (e) { toast('检索失败：' + e.message) }
}

function itemTitle(t, it) {
  if (t === 'semantic') return it.topic || it.id
  if (t === 'episodic') return it.task || '情景事件'
  return `[${it.session || 'default'}] ${(it.content || '').slice(0, 20)}`
}

function itemTime(t, it) {
  return it.updated_at || it.created_at || it.time || ''
}

function itemBody(t, it) {
  if (t === 'semantic') {
    const pts = (it.points || []).join('；')
    return `${pts}（置信度 ${it.confidence || 0}，来源 ${(it.sources || []).length} 条）`
  }
  if (t === 'episodic') {
    return `动作：${it.action || ''}｜结果：${it.result || ''}｜参与：${it.agents || '-'}`
  }
  return it.content || ''
}

onMounted(load)
</script>

<style scoped>
.page { padding: 20px 24px; }
.head-icon { width: 22px; height: 22px; border-radius: 6px; object-fit: cover; vertical-align: -4px; margin-right: 6px; }
.head-actions { display: flex; gap: 8px; }
.mem-icon { width: 18px; height: 18px; border-radius: 5px; object-fit: cover; vertical-align: -4px; }
.memory-body { display: flex; gap: 16px; height: calc(100vh - 150px); }
.mem-list { width: 240px; flex: 0 0 auto; overflow-y: auto; }
.mem-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mem-editor { flex: 1; min-width: 0; overflow-y: auto; }
.editor-panel { padding: 20px 24px; max-width: 720px; }
.detail-actions { display: flex; gap: 8px; }
.detail-empty { text-align: center; padding-top: 12vh; }
.detail-empty .detail-scene { margin: 14px auto 10px; max-width: 300px; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 30px var(--capy-primary-glow); opacity: .95; }
.detail-empty .detail-scene img { width: 100%; height: auto; display: block; }
.detail-empty .empty-logo { font-size: 56px; margin-bottom: 10px; }
.detail-empty .empty-logo img { width: 96px; height: 96px; border-radius: 28px; object-fit: cover; box-shadow: 0 8px 28px var(--capy-primary-glow); }
.detail-empty .empty-title { font-size: 20px; font-weight: 700; }
.detail-empty .empty-sub { color: var(--capy-text2); margin-top: 4px; }
.empty-tip { color: var(--capy-text2); text-align: center; padding: 20px 0; }

/* 三级记忆 */
.tier-side { width: 300px; flex: 0 0 auto; overflow-y: auto; padding-right: 4px; }
.tier-search { display: flex; gap: 8px; margin-bottom: 8px; }
.tier-search .input { flex: 1; min-width: 0; }
.dream-msg { background: var(--capy-panel, #fff); border: 1px solid var(--capy-border, #eee); border-radius: 8px; padding: 8px 10px; margin-bottom: 8px; color: var(--capy-primary, #8a5cf6); font-size: 13px; }
.dream-state { color: var(--capy-text2); font-size: 12px; margin-bottom: 12px; }
.query-results .tier-title { font-weight: 700; margin-bottom: 6px; }
.qr-item { border: 1px solid var(--capy-border, #eee); border-radius: 8px; padding: 8px 10px; margin-bottom: 8px; background: var(--capy-panel, #fff); }
.qr-title { font-weight: 600; font-size: 14px; }
.qr-snippet { color: var(--capy-text2); font-size: 12px; margin: 4px 0; }
.qr-meta { color: var(--capy-text3, #aaa); font-size: 11px; }
.tier-main { flex: 1; min-width: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
.tier-panel { padding: 14px 18px; }
.tier-head { display: flex; align-items: center; gap: 8px; font-weight: 700; margin-bottom: 8px; }
.tier-dot { width: 10px; height: 10px; border-radius: 50%; }
.tier-dot.tier-semantic { background: #8a5cf6; }
.tier-dot.tier-episodic { background: #2f9e6e; }
.tier-dot.tier-working { background: #d98c2f; }
.tier-item { border-top: 1px dashed var(--capy-border, #eee); padding: 8px 0; }
.tier-item-title { font-weight: 600; font-size: 14px; }
.tier-item-time { color: var(--capy-text3, #aaa); font-size: 11px; margin: 2px 0; }
.tier-item-body { color: var(--capy-text2); font-size: 12px; white-space: pre-wrap; word-break: break-all; }
.tier-badge { font-size: 11px; padding: 1px 6px; border-radius: 4px; }
.tier-badge.tier-semantic { background: rgba(138, 92, 246, 0.15); color: #8a5cf6; }
.tier-badge.tier-episodic { background: rgba(47, 158, 110, 0.15); color: #2f9e6e; }
.tier-badge.tier-working { background: rgba(217, 140, 47, 0.15); color: #d98c2f; }
</style>
