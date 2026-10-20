<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2><img class="head-icon" src="/images/capy/capy_gif02.gif" alt="进化" /> 自主进化</h2>
        <div class="sub">噜噜从任务台账里反思，把自己越用越顺手</div>
      </div>
      <div class="head-actions">
        <button class="btn evolve-btn" @click="runReflect" :disabled="busy">
          <img v-if="busy" class="btn-busy-img" src="/images/capy/capy_gif04.gif" alt="busy" />
          <img v-else class="btn-ico-img" src="/images/capy/capy_gif06.gif" alt="反思" />
          {{ busy ? '反思中…' : '触发反思' }}
        </button>
        <button class="btn btn-primary evolve-btn" @click="runImprove" :disabled="busy">
          <img v-if="busy" class="btn-busy-img" src="/images/capy/capy_gif04.gif" alt="busy" />
          <img v-else class="btn-ico-img" src="/images/capy/capy_gif01.gif" alt="改进" />
          {{ busy ? '改进中…' : '触发改进' }}
        </button>
        <button class="btn evolve-btn" @click="startAdd" :disabled="busy">
          <img class="btn-ico-img" src="/images/capy/capy_gif07.gif" alt="加经验" /> ＋ 手动加经验
        </button>
      </div>
    </div>

    <!-- 状态卡片 -->
    <div v-if="status" class="stat-cards">
      <div class="stat-card">
        <img class="stat-ico" src="/images/capy/capy_gif06.gif" alt="上次触发" />
        <div class="stat-body">
          <div class="stat-label">上次触发</div>
          <div class="stat-value">{{ status.last_time || '从未' }}</div>
        </div>
      </div>
      <div class="stat-card">
        <img class="stat-ico" src="/images/capy/capy05.png" alt="经验库" />
        <div class="stat-body">
          <div class="stat-label">经验库</div>
          <div class="stat-value">{{ status.lesson_count }} 条</div>
        </div>
      </div>
      <div class="stat-card">
        <img class="stat-ico" src="/images/capy/capy_gif01.gif" alt="已应用" />
        <div class="stat-body">
          <div class="stat-label">已应用</div>
          <div class="stat-value">{{ status.applied_total }} 次</div>
        </div>
      </div>
      <div class="stat-card">
        <img class="stat-ico" src="/images/capy/capy_gif02.gif" alt="进化日志" />
        <div class="stat-body">
          <div class="stat-label">进化日志</div>
          <div class="stat-value">{{ status.log_count }} 条</div>
        </div>
      </div>
      <div class="stat-card">
        <img class="stat-ico" src="/images/capy/capy04.png" alt="任务台账" />
        <div class="stat-body">
          <div class="stat-label">任务台账</div>
          <div class="stat-value">{{ status.current_task_count }} 条</div>
        </div>
      </div>
    </div>

    <!-- 操作反馈 -->
    <div v-if="msg" class="evolve-msg" :class="{ err: msgErr }">{{ msg }}</div>

    <!-- 经验库 -->
    <div class="capy-panel">
      <div class="panel-head">
        <span class="panel-title">经验库 <span class="badge">{{ stats.total }}</span></span>
        <span class="panel-sub">已应用 {{ stats.applied_total }} 次 · 平均置信度 {{ stats.avg_confidence }}</span>
        <input v-model="lessonQ" class="input filter-input" placeholder="筛选经验（触发条件 / 建议 / 来源）" />
      </div>

      <!-- 手动新增表单 -->
      <div v-if="adding" class="evolve-add capy-form">
        <div class="form-row">
          <input v-model="newTrigger" class="input grow" placeholder="触发条件（如：文件整理任务失败时）" />
          <input v-model="newAdvice" class="input grow" placeholder="建议（如：先检查目标目录是否存在）" />
        </div>
        <div class="form-row">
          <input v-model="newTaskRef" class="input grow" placeholder="来源任务（可选）" />
          <input v-model.number="newConfidence" type="number" min="0" max="1" step="0.05" class="input conf-input" placeholder="置信度 0~1" />
          <button class="btn btn-primary" @click="submitAdd" :disabled="busy">
            <img v-if="busy" class="btn-busy-img" src="/images/capy/capy_gif04.gif" alt="busy" /> 保存
          </button>
          <button class="btn" @click="adding = false">取消</button>
        </div>
      </div>

      <!-- 经验卡片列表 -->
      <div v-if="filteredLessons.length" class="lesson-grid">
        <div v-for="l in filteredLessons" :key="l.id" class="lesson-card">
          <div class="lesson-head">
            <span class="lesson-trigger" :title="l.trigger">{{ l.trigger }}</span>
            <span class="badge" :class="confCls(l.confidence)">置信度 {{ l.confidence }}</span>
          </div>
          <div class="lesson-advice" :title="l.advice">{{ l.advice }}</div>
          <div class="lesson-meta">
            <span class="badge badge-ok">已应用 {{ l.applied }} 次</span>
            <span class="badge badge-yellow" :title="l.task_ref">{{ l.task_ref || '来源任务 —' }}</span>
            <span class="lesson-time">{{ l.created_at }}</span>
          </div>
          <div class="lesson-foot">
            <button class="btn btn-danger btn-mini" @click="delLesson(l)">删除</button>
          </div>
        </div>
      </div>
      <div v-else class="empty-tip">
        <img class="empty-img" src="/images/capy/capy_gif05.gif" alt="空状态" />
        <div>经验库还是空的，点「触发反思」从任务台账沉淀经验～</div>
      </div>
    </div>

    <!-- 进化日志 -->
    <div class="capy-panel">
      <div class="panel-head">
        <span class="panel-title">进化日志 <span class="badge">{{ logStats.total }}</span></span>
        <span class="panel-sub">
          已应用 {{ logStats.by_status.applied || 0 }} · 待确认 {{ logStats.by_status.pending || 0 }} ·
          高风险 {{ logStats.by_risk.high || 0 }}
        </span>
      </div>
      <div class="tasks-table-wrap">
        <table class="tasks-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>风险</th>
              <th>状态</th>
              <th>触发条件</th>
              <th>建议</th>
              <th>改进内容</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!logs.length">
              <td colspan="7" class="tasks-empty">
                <img class="empty-img" src="/images/capy/capy_gif05.gif" alt="空状态" />
                <div>暂无进化日志。</div>
              </td>
            </tr>
            <tr v-for="e in logs" :key="e.id">
              <td class="cell-time">{{ e.ts }}</td>
              <td><span class="badge" :class="e.risk === 'high' ? 'badge-danger' : 'badge-ok'">{{ e.risk }}</span></td>
              <td><span class="badge" :class="statusCls(e.status)">{{ statusLabel(e.status) }}</span></td>
              <td class="cell-task" :title="e.trigger">{{ e.trigger }}</td>
              <td class="cell-result" :title="e.advice">{{ e.advice }}</td>
              <td class="cell-result" :title="e.suggestion">{{ e.suggestion || '—' }}</td>
              <td class="cell-result" :title="e.note">{{ e.note || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { evolveApi } from '../api'
import { toast } from '../composables/toast'

const lessons = ref([])
const stats = ref({ total: 0, applied_total: 0, avg_confidence: 0 })
const logs = ref([])
const logStats = ref({ total: 0, by_status: {}, by_risk: {} })
const status = ref(null)
const busy = ref(false)
const msg = ref('')
const msgErr = ref(false)
const adding = ref(false)
const lessonQ = ref('')
const newTrigger = ref('')
const newAdvice = ref('')
const newTaskRef = ref('')
const newConfidence = ref(0.5)

const STATUS_META = {
  applied: { label: '已应用', cls: 'badge-ok' },
  pending: { label: '待人工确认', cls: 'badge-yellow' },
  skipped: { label: '已跳过', cls: 'badge-off' },
}

const filteredLessons = computed(() => {
  const q = lessonQ.value.trim().toLowerCase()
  if (!q) return lessons.value
  return lessons.value.filter(l =>
    (l.trigger || '').toLowerCase().includes(q) ||
    (l.advice || '').toLowerCase().includes(q) ||
    (l.task_ref || '').toLowerCase().includes(q)
  )
})

function statusLabel(s) { return (STATUS_META[s] || {}).label || s }
function statusCls(s) { return (STATUS_META[s] || {}).cls || 'badge-off' }
function confCls(c) { return c >= 0.7 ? 'badge-ok' : (c >= 0.4 ? 'badge-yellow' : 'badge-off') }

function flash(text, isErr = false) {
  msg.value = text
  msgErr.value = isErr
  setTimeout(() => { msg.value = '' }, 5000)
}

async function refresh() {
  try {
    const [l, lg, st] = await Promise.all([evolveApi.lessons(), evolveApi.log(), evolveApi.status()])
    lessons.value = l.items || []
    stats.value = l.stats || {}
    logs.value = lg.items || []
    logStats.value = lg.stats || {}
    status.value = st
  } catch (e) {
    flash('加载失败：' + e.message, true)
  }
}

async function runReflect() {
  busy.value = true
  try {
    const r = await evolveApi.reflect(true, 20)
    flash(r.message || (r.triggered ? '反思完成' : r.reason || '未触发'))
    await refresh()
  } catch (e) {
    flash('反思失败：' + e.message, true)
  } finally {
    busy.value = false
  }
}

async function runImprove() {
  busy.value = true
  try {
    const r = await evolveApi.improve(true, 3)
    flash(r.message || (r.triggered ? '改进完成' : r.reason || '未触发'))
    await refresh()
  } catch (e) {
    flash('改进失败：' + e.message, true)
  } finally {
    busy.value = false
  }
}

function startAdd() {
  adding.value = true
  newTrigger.value = ''
  newAdvice.value = ''
  newTaskRef.value = ''
  newConfidence.value = 0.5
}

async function submitAdd() {
  if (!newTrigger.value.trim() || !newAdvice.value.trim()) {
    flash('触发条件与建议不能为空', true)
    return
  }
  busy.value = true
  try {
    const r = await evolveApi.addLesson({
      trigger: newTrigger.value.trim(),
      advice: newAdvice.value.trim(),
      task_ref: newTaskRef.value.trim(),
      confidence: newConfidence.value,
    })
    flash(r.message || '已入库')
    adding.value = false
    await refresh()
  } catch (e) {
    flash('新增失败：' + e.message, true)
  } finally {
    busy.value = false
  }
}

async function delLesson(l) {
  try {
    const r = await evolveApi.delLesson(l.id)
    flash(r.message || '已删除')
    await refresh()
  } catch (e) {
    flash('删除失败：' + e.message, true)
  }
}

onMounted(refresh)
</script>

<style scoped>
.head-icon { width: 22px; height: 22px; border-radius: 6px; object-fit: cover; vertical-align: -4px; margin-right: 6px; }
.btn-ico-img { width: 16px; height: 16px; border-radius: 4px; object-fit: cover; vertical-align: -3px; margin-right: 4px; }
.btn-busy-img { width: 16px; height: 16px; border-radius: 4px; object-fit: cover; vertical-align: -3px; margin-right: 4px; animation: spin-busy 1.2s linear infinite; }
@keyframes spin-busy { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* 统计卡片 */
.stat-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 14px; }
.stat-card {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px;
  background: var(--capy-glass-card, rgba(255,255,255,.55));
  border: 1px solid var(--capy-border-soft);
  border-radius: var(--capy-radius-md);
  box-shadow: var(--capy-shadow-soft, 0 2px 10px rgba(0,0,0,.04));
  transition: var(--capy-transition);
}
.stat-card:hover { transform: translateY(-2px); box-shadow: var(--capy-shadow-hover); }
.stat-ico { width: 38px; height: 38px; border-radius: 10px; object-fit: cover; flex: 0 0 auto; }
.stat-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.stat-label { font-size: 11px; color: var(--capy-text2); }
.stat-value { font-weight: 700; font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.evolve-btn { display: inline-flex; align-items: center; }
.evolve-msg {
  margin-bottom: 12px; padding: 10px 14px;
  border-radius: var(--capy-radius-md);
  background: var(--capy-primary-soft);
  border: 1px solid var(--capy-primary-border);
  font-size: 13px;
}
.evolve-msg.err { background: var(--capy-danger-soft, rgba(239, 112, 96, .15)); color: var(--capy-danger, #ef7060); }

/* 经验卡片 */
.lesson-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.lesson-card {
  display: flex; flex-direction: column; gap: 8px;
  padding: 14px 16px;
  background: var(--capy-glass-card, rgba(255,255,255,.5));
  border: 1px solid var(--capy-border-soft);
  border-radius: var(--capy-radius-md);
  transition: var(--capy-transition);
}
.lesson-card:hover { transform: translateY(-2px); box-shadow: var(--capy-shadow-hover); }
.lesson-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.lesson-trigger { font-weight: 700; font-size: 14px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lesson-advice { font-size: 13px; color: var(--capy-text2); min-height: 38px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.lesson-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 12px; }
.lesson-time { color: var(--capy-text2); margin-left: auto; }
.lesson-foot { display: flex; justify-content: flex-end; }
.btn-mini { padding: 2px 10px; font-size: 12px; }

/* 手动新增表单 */
.evolve-add { display: grid; gap: 10px; margin-bottom: 14px; padding: 14px 16px; }
.form-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.conf-input { width: 110px; }
.grow { flex: 1; min-width: 140px; }
.filter-input { width: 220px; margin-left: auto; }

.panel-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.panel-title { font-weight: 700; font-size: 14px; }
.panel-sub { font-size: 11px; color: var(--capy-text2); }
.empty-tip { color: var(--capy-text2); text-align: center; padding: 40px 0; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.empty-img { width: 96px; height: 96px; border-radius: 14px; object-fit: cover; opacity: .9; }
</style>
