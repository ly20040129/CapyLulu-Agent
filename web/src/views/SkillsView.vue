<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2><img class="head-icon" src="/lulu/5.png" alt="技能" /> 技能广场</h2>
        <div class="sub">噜噜掌握的专项技能，即插即用</div>
      </div>
      <button class="btn btn-primary" @click="showAdd = !showAdd">＋ 添加技能</button>
    </div>

    <div v-if="showAdd" class="capy-panel add-panel">
      <div class="row-fields">
        <div class="field">
          <label>名称</label>
          <input v-model="form.name" class="input" placeholder="如：通用点单" />
        </div>
        <div class="field">
          <label>类型</label>
          <select v-model="form.skill_type" class="input">
            <option value="command">command</option>
            <option value="api">api</option>
            <option value="workflow">workflow</option>
          </select>
        </div>
      </div>
      <div class="field">
        <label>描述</label>
        <textarea v-model="form.desc" class="input" rows="3" placeholder="这个技能能做什么？"></textarea>
      </div>
      <div class="detail-actions">
        <button class="btn btn-secondary" @click="showAdd = false">取消</button>
        <button class="btn btn-primary" @click="addSkill">保存</button>
      </div>
    </div>

    <div class="grid-list">
      <div v-for="s in skills" :key="s.name" class="capy-card skill-card">
        <div class="card-top">
          <div class="skill-name">{{ s.name }}</div>
          <span class="badge badge-yellow">{{ s.type }}</span>
        </div>
        <div class="skill-desc">{{ s.desc || '——' }}</div>
        <div class="card-foot">
          <div class="foot-left">
            <span class="badge">{{ s.source || 'manual' }}</span>
            <span v-if="s.tool" class="badge badge-green" title="AI 可直接调度的运行时工具">已接入 · {{ s.tool }}</span>
          </div>
          <button class="btn btn-ghost btn-icon btn-sm" @click="removeSkill(s)" title="删除"><img class="btn-icon-img" src="/lulu/7.png" alt="删除" /></button>
        </div>
      </div>
    </div>
    <div v-if="!skills.length" class="empty-tip">还没有技能，点右上角添加一个吧。</div>

    <!-- SKILL.md 技能运行时区 -->
    <div class="capy-panel md-panel">
      <div class="md-head">
        <div>
          <h3>SKILL.md 技能</h3>
          <div class="sub">data/skills/ 下的技能文件，含指令正文，AI 可按 manifest 直接调度执行</div>
        </div>
        <button class="btn btn-primary" @click="showCreate = !showCreate">＋ 创建技能</button>
      </div>

      <div v-if="showCreate" class="md-create">
        <div class="field">
          <label>名称</label>
          <input v-model="createForm.name" class="input" placeholder="如：会议纪要整理" />
        </div>
        <div class="field">
          <label>描述</label>
          <input v-model="createForm.desc" class="input" placeholder="这个技能能做什么？" />
        </div>
        <div class="field">
          <label>执行步骤</label>
          <textarea v-model="createForm.steps" class="input" rows="4" placeholder="1. 读取指定目录下的 .md 文件；&#10;2. 汇总要点；&#10;3. 生成纪要并保存。"></textarea>
        </div>
        <div class="detail-actions">
          <button class="btn btn-secondary" @click="showCreate = false">取消</button>
          <button class="btn btn-primary" @click="createSkillMd">生成 SKILL.md</button>
        </div>
      </div>

      <div v-if="mdFiles.length" class="md-list">
        <div v-for="f in mdFiles" :key="f.name" class="md-item">
          <div class="md-item-top">
            <div class="skill-name">{{ f.name }}</div>
            <span class="badge badge-yellow">{{ f.runtime || 'custom' }}</span>
          </div>
          <div class="skill-desc">{{ f.description || '——' }}</div>
          <div v-if="f.tools && f.tools.length" class="md-tools">
            <span v-for="t in f.tools" :key="t" class="badge badge-green">{{ t }}</span>
          </div>
          <button class="btn btn-ghost btn-sm md-toggle" @click="toggleDetail(f)">
            {{ f._open ? '收起详情' : '查看详情' }}
          </button>
          <pre v-if="f._open" class="md-content">{{ f.content }}</pre>
        </div>
      </div>
      <div v-else class="empty-tip">还没有 SKILL.md，点「创建技能」生成一个吧。</div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { skillsApi } from '../api'
import { toast } from '../composables/toast'

const skills = ref([])
const showAdd = ref(false)
const form = ref({ name: '', skill_type: 'command', desc: '' })

// SKILL.md 技能区状态
const mdFiles = ref([])
const showCreate = ref(false)
const createForm = ref({ name: '', desc: '', steps: '' })

async function load() {
  try {
    const r = await skillsApi.list()
    skills.value = r.items || []
  } catch (e) { toast('加载失败：' + e.message) }
}

async function loadFiles() {
  try {
    const r = await skillsApi.files()
    mdFiles.value = (r.items || []).map(x => ({ ...x, _open: false }))
  } catch (e) { toast('SKILL.md 加载失败：' + e.message) }
}

function toggleDetail(f) {
  f._open = !f._open
}

async function createSkillMd() {
  const { name, desc, steps } = createForm.value
  if (!name.trim() || !desc.trim()) { toast('名称与描述不能为空'); return }
  try {
    const r = await skillsApi.createSkill({ name, desc, steps })
    toast(r.message || '创建成功')
    showCreate.value = false
    createForm.value = { name: '', desc: '', steps: '' }
    await loadFiles()
    await load()
  } catch (e) { toast('创建失败：' + e.message) }
}

async function addSkill() {
  if (!form.value.name.trim() || !form.value.desc.trim()) { toast('名称与描述不能为空'); return }
  try {
    const r = await skillsApi.add(form.value)
    toast(r.message || '添加成功')
    showAdd.value = false
    form.value = { name: '', skill_type: 'command', desc: '' }
    await load()
  } catch (e) { toast('添加失败：' + e.message) }
}

async function removeSkill(s) {
  if (!window.confirm(`确定删除技能「${s.name}」？`)) return
  try {
    const r = await skillsApi.del(s.name)
    toast(r.message || '已删除')
    await load()
  } catch (e) { toast('删除失败：' + e.message) }
}

onMounted(() => { load(); loadFiles() })
</script>

<style scoped>
.page { padding: 20px 24px; }
.head-icon { width: 22px; height: 22px; border-radius: 6px; object-fit: cover; vertical-align: -4px; margin-right: 6px; }
.btn-icon-img { width: 16px; height: 16px; border-radius: 4px; object-fit: cover; vertical-align: -3px; }
.add-panel { margin-bottom: 16px; padding: 18px 20px; max-width: 720px; }
.row-fields { display: flex; gap: 12px; }
.row-fields .field { flex: 1; }
.detail-actions { display: flex; gap: 8px; }
.grid-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.skill-card { transition: var(--capy-transition); }
.skill-card:hover { transform: translateY(-2px); box-shadow: var(--capy-shadow-hover); }
.card-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.skill-name { font-weight: 700; font-size: 15px; }
.skill-desc { margin-top: 8px; font-size: 13px; color: var(--capy-text2); min-height: 40px; }
.card-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; }
.foot-left { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.badge-green { background: var(--capy-green, #3f9d63); color: #fff; }
.empty-tip { color: var(--capy-text2); text-align: center; padding: 40px 0; }

/* SKILL.md 技能区 */
.md-panel { margin-top: 20px; padding: 18px 20px; }
.md-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.md-head h3 { margin: 0; font-size: 15px; }
.md-create { display: grid; gap: 10px; max-width: 720px; margin-bottom: 14px; }
.md-list { display: grid; gap: 12px; }
.md-item { border: 1px solid var(--capy-border, #eee); border-radius: 10px; padding: 12px 14px; }
.md-item-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.md-tools { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
.md-toggle { margin-top: 8px; }
.md-content { margin-top: 8px; padding: 10px 12px; background: var(--capy-bg, #faf8f4); border-radius: 8px; font-size: 12px; white-space: pre-wrap; word-break: break-all; max-height: 320px; overflow: auto; }
</style>
