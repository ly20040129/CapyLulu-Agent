<template>
  <div class="team-view">
    <!-- 顶栏 -->
    <div class="page-head team-head">
      <div>
        <h2><img class="head-icon" src="/capy/capy06.png" alt="团队" /> 管家团队</h2>
        <div class="sub">分工明确的噜噜管家们，随时听你调度</div>
      </div>
      <div class="head-actions">
        <button class="btn btn-outline" @click="reloadAgents"><img class="btn-icon-img" src="/capy/capy_gif07.gif" alt="重载" /> 重载路由</button>
        <button class="btn btn-primary" @click="startCreate"><img class="btn-icon-img" src="/capy/capy_gif01.gif" alt="新增" /> 新增管家</button>
      </div>
    </div>

    <div class="team-body">
      <!-- 左：Agent 卡片列表（成员卡片：图标 + 职责 + 能力标签 + 工具 + 状态） -->
      <aside class="team-list-col">
        <input v-model="query" class="input search-input" placeholder="搜索管家名称 / 职责 / 能力…" />
        <div class="team-list">
          <AgentCard
            v-for="a in filtered" :key="a.name"
            :name="a.name" :role="a.role" :prompt="a.prompt"
            :keywords="a.keywords" :tools="a.tools"
            :capabilities="a.capabilities" :description="a.description" :icon="a.icon"
            :enabled="a.enabled"
            :active="!creating && selected !== null && a.name === selected.name"
            @select="selectAgent(a)"
          />
        </div>
      </aside>

      <!-- 右：详情 / 新增 -->
      <section class="team-detail">
        <div v-if="!selected && !creating" class="detail-empty">
          <div class="empty-logo"><img src="/capy/capy_gif06.gif" alt="团队" /></div>
          <div class="empty-title">选一位管家看看</div>
          <div class="empty-sub">点左侧卡片查看职责与配置，或直接新增一位管家</div>
        </div>

        <div v-else class="capy-panel detail-panel">
          <div class="detail-head">
            <h3>{{ creating ? '新增管家' : '编辑 · ' + selected.name }}</h3>
            <div v-if="!creating" class="detail-status">
              <span class="badge" :class="selected.enabled ? 'badge-ok' : 'badge-off'">{{ selected.enabled ? '启用中' : '已停用' }}</span>
            </div>
          </div>

          <div class="field">
            <label>名称</label>
            <input v-model="form.name" class="input" :disabled="!creating" placeholder="如：文件管家" />
          </div>
          <div class="field">
            <label>职责</label>
            <input v-model="form.role" class="input" placeholder="如：本地文件全能助手" />
          </div>
          <div class="field">
            <label>能力标签（逗号分隔，委派时按此匹配）</label>
            <input v-model="form.capabilities" class="input" placeholder="文件、整理、搜索、归档" />
          </div>
          <div class="field">
            <label>一句话职责（卡片摘要展示）</label>
            <input v-model="form.description" class="input" placeholder="负责本地文件的查找、整理与归档" />
          </div>
          <div class="row-fields">
            <div class="field">
              <label>头像图标（路径或 URL）</label>
              <input v-model="form.icon" class="input" placeholder="/lulu/6.png" />
            </div>
            <div class="field">
              <label>关键词（逗号分隔）</label>
              <input v-model="form.keywords" class="input" placeholder="文件、查找、整理" />
            </div>
          </div>
          <div class="field">
            <label>可用工具（逗号分隔）</label>
            <input v-model="form.tools" class="input" placeholder="read、write、search" />
          </div>
          <div class="field">
            <label>提示词（角色设定）</label>
            <textarea v-model="form.prompt" class="input" rows="6" placeholder="设定这位管家的行为与能力边界…"></textarea>
          </div>

          <div class="detail-actions">
            <button class="btn btn-secondary" @click="cancelEdit">取消</button>
            <button v-if="!creating" class="btn btn-primary" @click="saveUpdate">保存修改</button>
            <button v-if="creating" class="btn btn-primary" @click="saveCreate">创建管家</button>
            <button v-if="!creating" class="btn btn-danger" @click="askRemove">删除管家</button>
          </div>
          <div v-if="!creating" class="toggle-row">
            <span>启用 / 停用</span>
            <label class="switch">
              <input type="checkbox" :checked="selected.enabled" @change="toggleSelected($event)" />
              <span class="track"></span>
            </label>
          </div>
        </div>
      </section>
    </div>

    <!-- 任务台账面板 -->
    <div class="capy-panel tasks-panel">
      <div class="tasks-head">
        <div>
          <h3><img class="head-icon" src="/capy/capy04.png" alt="台账" /> 任务台账</h3>
          <div class="sub">每次委派留痕：时间 / 任务 / 负责管家 / 状态 / 结果 / 耗时，供复盘与记忆蒸馏</div>
        </div>
        <div class="tasks-actions">
          <input v-model="dispatchText" class="input dispatch-input" placeholder="输入任务描述，测试委派（可留空管家自动匹配能力）…" @keyup.enter="doDispatch" />
          <input v-model="dispatchAgent" class="input dispatch-agent" placeholder="指定管家（可留空）" />
          <button class="btn btn-primary" :disabled="dispatching" @click="doDispatch">{{ dispatching ? '委派中…' : '委派测试' }}</button>
          <button class="btn btn-outline" @click="reloadTasks">刷新</button>
          <button class="btn btn-danger" @click="askClearTasks">清空</button>
        </div>
      </div>

      <div class="stats-row">
        <span class="stat-chip" v-for="(n, k) in taskStats" :key="k">
          <span class="badge" :class="badgeCls(k)">{{ statusLabel(k) }}</span> {{ n }}
        </span>
      </div>

      <div v-if="dispatchResult" class="dispatch-result">
        <span class="badge" :class="badgeCls(dispatchResult.status)">{{ statusLabel(dispatchResult.status) }}</span>
        <b>{{ dispatchResult.agent }}</b>
        <span class="dispatch-msg">{{ dispatchResult.message }}</span>
        <span class="dispatch-reply">{{ dispatchResult.result }}</span>
      </div>

      <div class="tasks-table-wrap">
        <table class="tasks-table">
          <thead>
            <tr>
              <th>时间</th><th>任务</th><th>负责管家</th><th>状态</th><th>耗时</th><th>结果摘要</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!tasks.length">
              <td colspan="6" class="tasks-empty">
                <img class="empty-img" src="/capy/capy_gif05.gif" alt="空状态" />
                <div>暂无任务台账，去上方「委派测试」试一发～</div>
              </td>
            </tr>
            <tr v-for="t in tasks" :key="t.id">
              <td class="cell-time">{{ t.time }}</td>
              <td class="cell-task" :title="t.task">{{ t.task }}</td>
              <td>{{ t.agent }}</td>
              <td><span class="badge" :class="badgeCls(t.status)">{{ statusLabel(t.status) }}</span></td>
              <td>{{ t.duration_ms != null ? t.duration_ms + ' ms' : '—' }}</td>
              <td class="cell-result" :title="t.result">{{ t.result || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AgentCard from '../components/AgentCard.vue'
import { teamApi } from '../api'
import { toast } from '../composables/toast'

const agents = ref([])
const query = ref('')
const selected = ref(null)
const creating = ref(false)
const form = ref({ name: '', role: '', prompt: '', keywords: '', tools: '', capabilities: '', description: '', icon: '' })

// 任务台账
const tasks = ref([])
const taskStats = ref({})
const dispatchText = ref('')
const dispatchAgent = ref('')
const dispatchResult = ref(null)
const dispatching = ref(false)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return agents.value
  return agents.value.filter(a =>
    a.name.toLowerCase().includes(q) ||
    (a.role || '').toLowerCase().includes(q) ||
    (a.keywords || '').toLowerCase().includes(q) ||
    (a.capabilities || '').toLowerCase().includes(q) ||
    (a.description || '').toLowerCase().includes(q)
  )
})

const STATUS_MAP = {
  assigned: { label: '已派发', cls: 'badge-yellow' },
  running: { label: '执行中', cls: 'badge-yellow' },
  done: { label: '已完成', cls: 'badge-ok' },
  failed: { label: '失败', cls: 'badge-danger' },
  escalated: { label: '升级兜底', cls: 'badge' },
}
const statusLabel = (s) => (STATUS_MAP[s] || { label: s || '—' }).label
const badgeCls = (s) => (STATUS_MAP[s] || { cls: 'badge' }).cls

async function reloadAgents() {
  try {
    const r = await teamApi.agents()
    agents.value = r.items || []
    if (selected.value) {
      selected.value = agents.value.find(a => a.name === selected.value.name) || null
    }
    toast('管家列表已刷新')
  } catch (e) {
    toast('加载失败：' + e.message)
  }
}

async function reloadTasks() {
  try {
    const r = await teamApi.tasks()
    tasks.value = r.items || []
    taskStats.value = r.stats || {}
  } catch (e) {
    toast('台账加载失败：' + e.message)
  }
}

function selectAgent(a) {
  selected.value = { ...a }
  creating.value = false
  form.value = {
    name: a.name, role: a.role, prompt: a.prompt,
    keywords: (a.keywords || []).join(', '), tools: (a.tools || []).join(', '),
    capabilities: (a.capabilities || []).join(', '),
    description: a.description || '',
    icon: a.icon || '',
  }
}

function startCreate() {
  creating.value = true
  selected.value = null
  form.value = { name: '', role: '', prompt: '', keywords: '', tools: '', capabilities: '', description: '', icon: '' }
}

function cancelEdit() {
  if (creating.value) { creating.value = false; return }
  if (selected.value) selectAgent(selected.value)
}

async function saveCreate() {
  if (!form.value.name.trim() || !form.value.role.trim()) {
    toast('名称与职责不能为空'); return
  }
  try {
    const r = await teamApi.add(form.value)
    toast(r.message || '创建成功')
    creating.value = false
    await reloadAgents()
    const created = agents.value.find(a => a.name === form.value.name)
    if (created) selectAgent(created)
  } catch (e) {
    toast('创建失败：' + e.message)
  }
}

async function saveUpdate() {
  if (!selected.value) return
  try {
    const r = await teamApi.update(selected.value.name, form.value)
    toast(r.message || '已保存')
    await reloadAgents()
  } catch (e) {
    toast('保存失败：' + e.message)
  }
}

async function toggleSelected(ev) {
  if (!selected.value) return
  const enabled = ev.target.checked
  try {
    const r = await teamApi.toggle(selected.value.name, enabled)
    toast(r.message || (enabled ? '已启用' : '已停用'))
    selected.value.enabled = enabled
    await reloadAgents()
  } catch (e) {
    ev.target.checked = !enabled
    toast('操作失败：' + e.message)
  }
}

function askRemove() {
  if (!selected.value) return
  if (window.confirm(`确定删除管家「${selected.value.name}」？删除后不可恢复。`)) {
    doRemove(selected.value.name)
  }
}

async function doRemove(name) {
  try {
    const r = await teamApi.del(name)
    toast(r.message || '已删除')
    selected.value = null
    await reloadAgents()
  } catch (e) {
    toast('删除失败：' + e.message)
  }
}

async function doDispatch() {
  const task = dispatchText.value.trim()
  if (!task) { toast('请输入任务描述'); return }
  dispatching.value = true
  dispatchResult.value = null
  try {
    const r = await teamApi.dispatchTest({ agent: dispatchAgent.value.trim(), task })
    dispatchResult.value = r
    toast(r.message || '委派完成')
    await reloadTasks()
  } catch (e) {
    toast('委派失败：' + e.message)
  } finally {
    dispatching.value = false
  }
}

function askClearTasks() {
  if (window.confirm('确定清空全部任务台账？清空后不可恢复。')) {
    doClearTasks()
  }
}

async function doClearTasks() {
  try {
    const r = await teamApi.clearTasks()
    toast(r.message || '已清空')
    tasks.value = []
    taskStats.value = {}
    dispatchResult.value = null
  } catch (e) {
    toast('清空失败：' + e.message)
  }
}

onMounted(() => {
  reloadAgents()
  reloadTasks()
})
</script>

<style scoped>
.team-view { padding: 20px 24px; height: 100%; display: flex; flex-direction: column; gap: 14px; overflow: hidden; }
.team-head { flex: 0 0 auto; }
.head-icon { width: 22px; height: 22px; border-radius: 6px; object-fit: cover; vertical-align: -4px; margin-right: 6px; }
.btn-icon-img { width: 16px; height: 16px; border-radius: 4px; object-fit: cover; vertical-align: -3px; margin-right: 4px; }
.head-actions { display: flex; gap: 8px; }

.team-body { flex: 1; min-height: 0; display: flex; gap: 16px; }

.team-list-col {
  width: 300px; flex: 0 0 auto;
  display: flex; flex-direction: column; gap: 10px;
  min-height: 0;
}
.search-input { flex: 0 0 auto; }
.team-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding-right: 4px; }

.team-detail { flex: 1; min-width: 0; overflow-y: auto; }
.detail-panel { padding: 20px 24px; max-width: 720px; }
.detail-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.detail-head h3 { margin: 0; font-size: 18px; }
.row-fields { display: flex; gap: 12px; }
.row-fields .field { flex: 1; }
.detail-actions { display: flex; gap: 8px; margin-top: 4px; }
.toggle-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 18px; padding-top: 14px;
  border-top: 1px solid var(--capy-border-soft);
  font-size: 14px;
}
.detail-empty {
  text-align: center; padding: 48px 24px;
  background: var(--capy-glass-card, rgba(255,255,255,.45));
  border: 1px solid var(--capy-border-soft);
  border-radius: var(--capy-radius-md);
  box-shadow: var(--capy-shadow-soft, 0 2px 10px rgba(0,0,0,.04));
}
.detail-empty .empty-logo img { width: 96px; height: 96px; border-radius: 16px; object-fit: cover; opacity: .9; box-shadow: 0 8px 28px var(--capy-primary-glow); }
.detail-empty .empty-title { font-size: 20px; font-weight: 700; margin-top: 8px; }
.detail-empty .empty-sub { color: var(--capy-text2); margin-top: 4px; }

/* 任务台账 */
.tasks-panel { flex: 0 0 auto; padding: 14px 18px; display: flex; flex-direction: column; gap: 10px; max-height: 42%; }
.tasks-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.tasks-head h3 { margin: 0; font-size: 16px; }
.tasks-actions { display: flex; gap: 6px; align-items: center; }
.dispatch-input { width: 320px; }
.dispatch-agent { width: 130px; }
.stats-row { display: flex; gap: 10px; flex-wrap: wrap; }
.stat-chip {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--capy-text2);
  padding: 4px 10px; border-radius: 999px;
  background: var(--capy-glass, rgba(255,255,255,.4));
  border: 1px solid var(--capy-border-soft);
}
.dispatch-result {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  font-size: 13px; background: var(--capy-primary-soft);
  border: 1px solid var(--capy-primary-border); border-radius: var(--capy-radius-md);
  padding: 8px 10px;
}
.dispatch-msg { color: var(--capy-text2); }
.dispatch-reply {
  flex-basis: 100%; color: var(--capy-text2); font-size: 12px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.tasks-table-wrap { overflow: auto; min-height: 0; }
.tasks-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.tasks-table th, .tasks-table td {
  text-align: left; padding: 6px 8px;
  border-bottom: 1px solid var(--capy-border-soft);
  white-space: nowrap;
}
.tasks-table th { color: var(--capy-text2); font-weight: 600; position: sticky; top: 0; background: var(--capy-card); }
.cell-task { max-width: 300px; overflow: hidden; text-overflow: ellipsis; }
.cell-result { max-width: 320px; overflow: hidden; text-overflow: ellipsis; }
.cell-time { color: var(--capy-text2); font-size: 11px; }
.tasks-empty { text-align: center; color: var(--capy-text2); padding: 24px 0; }
.empty-img { width: 96px; height: 96px; border-radius: 14px; object-fit: cover; opacity: .9; margin-bottom: 6px; }
</style>
