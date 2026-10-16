<template>
  <div class="kb-view">
    <!-- 左：知识库列表 -->
    <aside class="kb-side">
      <div class="panel-title">知识库</div>
      <div class="kb-create">
        <input v-model="newKbName" class="input" placeholder="新建库名称"
               @keyup.enter="createKb" />
        <button class="btn btn-primary btn-sm" @click="createKb">新建</button>
      </div>
      <div class="kb-list">
        <div v-for="k in kbs" :key="k.name" class="kb-card"
             :class="{ active: current === k.name }" @click="select(k.name)">
          <div class="kb-card-main">
            <div class="kb-card-name">{{ k.name }}</div>
            <div class="kb-card-meta">{{ k.doc_count }} 文档 · {{ k.chunk_count }} 块</div>
          </div>
          <button class="btn-icon" title="删除知识库" @click.stop="delKb(k.name)">✕</button>
        </div>
        <div v-if="!kbs.length" class="empty-tip">还没有知识库，先新建一个吧</div>
      </div>
    </aside>

    <!-- 右：库详情 -->
    <main class="kb-main">
      <template v-if="current">
        <div class="kb-head">
          <div>
            <div class="panel-title">{{ current }}</div>
            <div class="kb-head-meta">文档管理 · 搜索 · 问答</div>
          </div>
          <label class="btn btn-primary btn-sm">
            上传文档
            <input type="file" class="hidden-file" multiple @change="onUpload" />
          </label>
        </div>

        <div class="capy-section">
          <div class="section-title">库内文档</div>
          <table class="tbl" v-if="docs.length">
            <thead><tr><th>文件名</th><th>大小</th><th>块数</th><th>导入时间</th><th></th></tr></thead>
            <tbody>
              <tr v-for="d in docs" :key="d.doc_id">
                <td>{{ d.name }}</td>
                <td>{{ fmtSize(d.size) }}</td>
                <td>{{ d.chunk_count }}</td>
                <td>{{ d.imported_at }}</td>
                <td><button class="btn-icon" title="删除文档" @click="delDoc(d.doc_id)">✕</button></td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty-tip">暂无文档，点击右上角「上传文档」导入（txt/md/csv/json/pdf）</div>
        </div>

        <div class="capy-section">
          <div class="section-title">关键词搜索</div>
          <div class="q-row">
            <input v-model="searchQ" class="input" placeholder="输入关键词，检索库内文档块"
                   @keyup.enter="doSearch" />
            <button class="btn btn-primary btn-sm" @click="doSearch">搜索</button>
          </div>
          <div class="hit-list" v-if="searchHits.length">
            <div v-for="(h, i) in searchHits" :key="i" class="hit-item">
              <div class="hit-src">{{ h.source }} · 相关度 {{ h.score }}</div>
              <div class="hit-text">{{ h.text }}</div>
            </div>
          </div>
          <div v-else-if="searched" class="empty-tip">未找到相关片段</div>
        </div>

        <div class="capy-section">
          <div class="section-title">知识问答（LLM）</div>
          <div class="q-row">
            <input v-model="askQ" class="input" placeholder="基于知识库提问，如：这个库讲了什么？"
                   @keyup.enter="doAsk" />
            <button class="btn btn-primary btn-sm" @click="doAsk">提问</button>
          </div>
          <div v-if="answer" class="answer-box">
            <div class="answer-text">{{ answer.answer }}</div>
            <div v-if="answer.sources && answer.sources.length" class="answer-src">
              <div class="answer-src-title">来源：</div>
              <div v-for="(s, i) in answer.sources" :key="i" class="answer-src-item">
                {{ s.source }}：{{ s.snippet }}
              </div>
            </div>
            <div class="answer-mode">模式：{{ answer.mode }}</div>
          </div>
        </div>
      </template>

      <div v-else class="empty-main">
        <div class="panel-title">知识库</div>
        <p>在左侧选择或新建一个知识库，然后上传文档、检索与问答。</p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { kbApi } from '../api'
import { provideToast } from '../composables/toast'

const toast = provideToast()

const kbs = ref([])
const current = ref('')
const newKbName = ref('')
const docs = ref([])
const searchQ = ref('')
const searchHits = ref([])
const searched = ref(false)
const askQ = ref('')
const answer = ref(null)

async function loadKbs() {
  try {
    const r = await kbApi.list()
    kbs.value = r.kbs || []
    if (current.value && !kbs.value.find((k) => k.name === current.value)) current.value = ''
  } catch (e) { toast('加载知识库失败：' + e.message) }
}

async function createKb() {
  const name = newKbName.value.trim()
  if (!name) { toast('请输入知识库名称'); return }
  try {
    const r = await kbApi.create(name)
    toast(r.message || '已创建')
    newKbName.value = ''
    await loadKbs()
    current.value = name
    await loadDocs()
  } catch (e) { toast('创建失败：' + e.message) }
}

async function delKb(name) {
  if (!confirm(`确定删除知识库「${name}」？库内所有文档将一并删除。`)) return
  try {
    await kbApi.del(name)
    if (current.value === name) { current.value = ''; docs.value = [] }
    await loadKbs()
    toast('已删除知识库')
  } catch (e) { toast('删除失败：' + e.message) }
}

function select(name) {
  current.value = name
  loadDocs()
}

async function loadDocs() {
  if (!current.value) return
  try {
    const r = await kbApi.docs(current.value)
    docs.value = r.docs || []
  } catch (e) { toast('加载文档失败：' + e.message) }
}

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader()
    fr.onload = () => resolve(fr.result)
    fr.onerror = () => reject(fr.error)
    fr.readAsText(file)
  })
}

function readFileAsB64(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader()
    fr.onload = () => {
      const bytes = new Uint8Array(fr.result)
      let bin = ''
      for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i])
      resolve(btoa(bin))
    }
    fr.onerror = () => reject(fr.error)
    fr.readAsArrayBuffer(file)
  })
}

async function onUpload(ev) {
  const files = ev.target.files || []
  ev.target.value = ''
  for (const file of files) {
    try {
      const isPdf = /\.pdf$/i.test(file.name)
      const body = { name: file.name }
      if (isPdf) body.content_b64 = await readFileAsB64(file)
      else body.content = await readFileAsText(file)
      const r = await kbApi.addDoc(current.value, body)
      toast(r.message || '导入成功')
    } catch (e) { toast(`「${file.name}」导入失败：` + e.message) }
  }
  await loadDocs()
}

async function delDoc(docId) {
  if (!confirm('确定删除该文档？')) return
  try {
    await kbApi.delDoc(current.value, docId)
    await loadDocs()
    toast('已删除文档')
  } catch (e) { toast('删除失败：' + e.message) }
}

async function doSearch() {
  const q = searchQ.value.trim()
  if (!q) { toast('请输入关键词'); return }
  try {
    const r = await kbApi.search(q, current.value, 5)
    searchHits.value = r.hits || []
    searched.value = true
  } catch (e) { toast('搜索失败：' + e.message) }
}

async function doAsk() {
  const q = askQ.value.trim()
  if (!q) { toast('请输入问题'); return }
  try {
    answer.value = await kbApi.ask({ kb: current.value, question: q, top_k: 5 })
  } catch (e) { toast('问答失败：' + e.message) }
}

function fmtSize(bytes) {
  if (!bytes && bytes !== 0) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

onMounted(loadKbs)
</script>

<style scoped>
.kb-view { display: flex; height: 100%; min-height: 0; }
.kb-side {
  width: 240px; flex: 0 0 auto; padding: 16px 12px;
  border-right: 1px solid var(--capy-border-soft);
  background: var(--capy-glass-sidebar);
  display: flex; flex-direction: column; gap: 12px;
  overflow-y: auto;
}
.kb-main { flex: 1; min-width: 0; padding: 18px 22px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }
.panel-title { font-size: 16px; font-weight: 700; }
.kb-create { display: flex; gap: 6px; }
.kb-create .input { flex: 1; }
.kb-list { display: flex; flex-direction: column; gap: 8px; }
.kb-card {
  display: flex; align-items: center; justify-content: space-between; gap: 6px;
  padding: 10px 12px; border-radius: var(--capy-radius-md);
  border: 1px solid var(--capy-border-soft);
  background: var(--capy-primary-soft2);
  cursor: pointer; transition: var(--capy-transition);
}
.kb-card:hover { border-color: var(--capy-primary-border); }
.kb-card.active { border-color: var(--capy-primary-border); box-shadow: inset 0 0 0 1px var(--capy-primary-border); background: var(--capy-primary-soft); }
.kb-card-name { font-weight: 600; font-size: 13px; word-break: break-all; }
.kb-card-meta { font-size: 11px; color: var(--capy-text2); }
.kb-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.kb-head-meta { font-size: 12px; color: var(--capy-text2); }
.capy-section { padding: 14px 16px; border-radius: var(--capy-radius-md); border: 1px solid var(--capy-border-soft); background: var(--capy-glass-sidebar); }
.section-title { font-weight: 700; margin-bottom: 10px; font-size: 14px; }
.q-row { display: flex; gap: 8px; margin-bottom: 10px; }
.q-row .input { flex: 1; }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { padding: 7px 8px; border-bottom: 1px solid var(--capy-border-soft); text-align: left; }
.tbl th { color: var(--capy-text2); font-weight: 600; }
.hit-list { display: flex; flex-direction: column; gap: 8px; }
.hit-item { padding: 10px 12px; border: 1px solid var(--capy-border-soft); border-radius: var(--capy-radius-md); background: var(--capy-primary-soft2); }
.hit-src { font-size: 12px; color: var(--capy-yellow); margin-bottom: 4px; }
.hit-text { font-size: 13px; white-space: pre-wrap; word-break: break-all; }
.answer-box { padding: 12px 14px; border: 1px solid var(--capy-primary-border); border-radius: var(--capy-radius-md); background: var(--capy-primary-soft); }
.answer-text { font-size: 14px; white-space: pre-wrap; margin-bottom: 10px; }
.answer-src-title { font-size: 12px; color: var(--capy-text2); margin-bottom: 4px; }
.answer-src-item { font-size: 12px; color: var(--capy-text2); padding: 3px 0; border-top: 1px dashed var(--capy-border-soft); }
.answer-mode { margin-top: 8px; font-size: 11px; color: var(--capy-text2); }
.empty-tip { color: var(--capy-text2); font-size: 13px; padding: 8px 0; }
.empty-main { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: var(--capy-text2); }
.btn-icon { background: none; border: none; color: var(--capy-text2); cursor: pointer; font-size: 14px; }
.btn-icon:hover { color: var(--capy-danger); }
.hidden-file { display: none; }
</style>
