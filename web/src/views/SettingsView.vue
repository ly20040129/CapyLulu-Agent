<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2><img class="head-icon" src="/images/lulu/1.png" alt="设置" /> 模型设置</h2>
        <div class="sub">给噜噜接上大脑，它才能正经干活</div>
      </div>
      <span class="badge" :class="ready ? 'badge-ok' : 'badge-danger'">{{ ready ? '已就绪' : '未配置' }}</span>
    </div>

    <div class="capy-panel settings-panel">
      <div class="status-line">{{ modelStatus }}</div>

      <div class="field">
        <label>服务商</label>
        <select v-model="form.provider" class="input">
          <option v-for="p in providers" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>
      <div class="field">
        <label>API Key</label>
        <input v-model="form.api_key" type="password" class="input" placeholder="sk-…" autocomplete="off" />
      </div>
      <div class="row-fields">
        <div class="field">
          <label>模型名</label>
          <input v-model="form.model" class="input" placeholder="如 glm-4-plus / deepseek-chat" />
        </div>
        <div class="field">
          <label>Base URL（可选）</label>
          <input v-model="form.base_url" class="input" placeholder="留空使用服务商默认" />
        </div>
      </div>

      <div class="field">
        <label>界面配色</label>
        <div class="palette-row">
          <button
            v-for="p in palettes" :key="p"
            class="palette-chip" :class="{ active: p === palette }"
            @click="switchPalette(p)"
          >{{ p }}</button>
        </div>
      </div>

      <div class="detail-actions">
        <button class="btn btn-primary" @click="saveLlm">保存并应用</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { settingsApi } from '../api'
import { toast } from '../composables/toast'

const form = ref({ provider: 'zhipu', api_key: '', model: '', base_url: '' })
const providers = ref([])
const palettes = ref([])
const palette = ref('琥珀暖暗')
const ready = ref(false)
const modelStatus = ref('')

function applyPalette(name) {
  document.body.dataset.palette = name
  localStorage.setItem('capy-palette', name)
  palette.value = name
}

async function switchPalette(name) {
  try { await settingsApi.palette(name) } catch (e) { /* 本地也生效 */ }
  applyPalette(name)
  toast('配色已切换：' + name)
}

async function saveLlm() {
  if (!form.value.api_key.trim()) { toast('API Key 不能为空'); return }
  try {
    const r = await settingsApi.llm(form.value)
    toast(r.message || '已保存')
    ready.value = true
    modelStatus.value = r.model_status || ''
  } catch (e) { toast('保存失败：' + e.message) }
}

onMounted(async () => {
  try {
    const r = await settingsApi.get()
    form.value.provider = r.provider
    providers.value = r.providers || []
    palettes.value = r.palettes || []
    ready.value = r.llm_ready
    modelStatus.value = r.model_status || ''
    applyPalette(r.palette)
  } catch (e) { toast('设置加载失败：' + e.message) }
})
</script>

<style scoped>
.page { padding: 20px 24px; }
.head-icon { width: 22px; height: 22px; border-radius: 6px; object-fit: cover; vertical-align: -4px; margin-right: 6px; }
.settings-panel { padding: 20px 24px; max-width: 680px; }
.status-line { margin-bottom: 14px; color: var(--capy-text2); font-size: 13px; }
.row-fields { display: flex; gap: 12px; }
.row-fields .field { flex: 1; }
.palette-row { display: flex; flex-wrap: wrap; gap: 8px; }
.palette-chip {
  padding: 6px 14px;
  border-radius: var(--capy-radius-pill);
  border: 1px solid var(--capy-border-soft);
  background: var(--capy-card2);
  color: var(--capy-text2);
  font-size: 13px;
  transition: var(--capy-transition);
}
.palette-chip:hover { border-color: var(--capy-primary-border); }
.palette-chip.active { background: var(--capy-primary-soft); border-color: var(--capy-yellow); color: var(--capy-yellow); font-weight: 600; }
.detail-actions { margin-top: 8px; }
</style>
