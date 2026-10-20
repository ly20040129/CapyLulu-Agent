<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2><img class="head-icon" src="/images/lulu/7.png" alt="工具" /> 工具记录</h2>
        <div class="sub">噜噜最近调用了哪些工具，一目了然</div>
      </div>
      <button class="btn btn-danger" @click="clearLogs">清空记录</button>
    </div>

    <div class="capy-panel log-panel">
      <div class="log-line" v-for="(l, i) in logs" :key="i">{{ l }}</div>
      <div v-if="!logs.length" class="empty-tip">还没有工具记录。</div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { toolsApi } from '../api'
import { toast } from '../composables/toast'

const logs = ref([])

async function load() {
  try {
    const r = await toolsApi.logs(240)
    logs.value = (r.items || []).slice().reverse()
  } catch (e) { toast('加载失败：' + e.message) }
}

async function clearLogs() {
  if (!window.confirm('确定清空全部工具记录？')) return
  try {
    await toolsApi.clear()
    logs.value = []
    toast('记录已清空')
  } catch (e) { toast('清空失败：' + e.message) }
}

onMounted(load)
</script>

<style scoped>
.page { padding: 20px 24px; }
.head-icon { width: 22px; height: 22px; border-radius: 6px; object-fit: cover; vertical-align: -4px; margin-right: 6px; }
.log-panel { max-height: calc(100vh - 170px); overflow-y: auto; font-family: Consolas, 'Cascadia Mono', monospace; font-size: 12.5px; }
.log-line { padding: 6px 4px; border-bottom: 1px dashed var(--capy-border-soft); white-space: pre-wrap; word-break: break-word; }
.empty-tip { color: var(--capy-text2); text-align: center; padding: 30px 0; }
</style>
