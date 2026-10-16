<template>
  <div class="agent-card" :class="{ active, off: !enabled }" @click="$emit('select')">
    <div class="card-top">
      <img class="agent-avatar" :src="avatar" :alt="name" />
      <div class="grow">
        <div class="agent-name">{{ name }}</div>
        <div class="agent-role">{{ role }}</div>
      </div>
      <span class="badge" :class="enabled ? 'badge-ok' : 'badge-off'">{{ enabled ? '启用' : '停用' }}</span>
    </div>
    <div class="agent-desc">{{ desc }}</div>
    <div v-if="caps.length" class="cap-row">
      <span v-for="c in caps" :key="c" class="cap-tag">{{ c }}</span>
    </div>
    <div class="card-foot">
      <span class="badge badge-yellow"><img class="tag-icon" src="/lulu/7.png" alt="工具" /> {{ toolsLabel }}</span>
      <span class="badge">{{ kwLabel }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, default: '' },
  role: { type: String, default: '' },
  prompt: { type: String, default: '' },
  keywords: { type: String, default: '' },
  tools: { type: String, default: '' },
  capabilities: { type: [String, Array], default: '' },
  description: { type: String, default: '' },
  icon: { type: String, default: '' },
  enabled: { type: Boolean, default: true },
  active: { type: Boolean, default: false },
})

defineEmits(['select'])

const avatar = computed(() => {
  const custom = asStr(props.icon).trim()
  if (custom && (custom.startsWith('/') || custom.startsWith('http'))) return custom
  const map = { '文件': '/lulu/6.png', '搜索': '/lulu/7.png', '代码': '/lulu/1.png', '办公': '/lulu/3.png', '团队': '/lulu/2.png', '主管': '/lulu/4.png', '客服': '/lulu/5.png' }
  for (const k of Object.keys(map)) if (props.role.includes(k)) return map[k]
  return '/lulu/1.png'
})
const asStr = (v) => {
  if (Array.isArray(v)) return v.join(', ')
  return v || ''
}
const desc = computed(() => {
  const d = asStr(props.description).trim()
  if (d) return d
  return (props.prompt || '').split('\n')[0] || '——'
})
const caps = computed(() => asStr(props.capabilities).split(/[,，]/).map(s => s.trim()).filter(Boolean).slice(0, 4))
const toolsLabel = computed(() => {
  const t = asStr(props.tools).trim()
  return t ? t.split(/[,，]/).filter(Boolean).slice(0, 2).join(' / ') : '系统'
})
const kwLabel = computed(() => {
  const k = asStr(props.keywords).trim()
  return k ? k.split(/[,，]/).filter(Boolean).slice(0, 2).join(' / ') : '通用'
})
</script>

<style scoped>
.agent-card {
  background: var(--capy-card);
  border: 1px solid var(--capy-border-soft);
  border-radius: var(--capy-radius-lg);
  padding: 14px;
  cursor: pointer;
  transition: var(--capy-transition);
}
.agent-card:hover { transform: translateY(-2px); box-shadow: var(--capy-shadow-hover); }
.agent-card.active { border-color: var(--capy-yellow); box-shadow: 0 0 0 2px var(--capy-primary-soft), var(--capy-shadow-card); }
.agent-card.off { opacity: .62; }
.card-top { display: flex; align-items: center; gap: 10px; }
.agent-avatar {
  width: 40px; height: 40px; flex: 0 0 auto;
  border-radius: var(--capy-radius-md);
  object-fit: cover;
  border: 1px solid var(--capy-primary-border);
}
.grow { flex: 1; min-width: 0; }
.agent-name { font-weight: 700; font-size: 15px; }
.agent-role { font-size: 12px; color: var(--capy-text2); }
.agent-desc {
  margin-top: 8px; font-size: 12px; color: var(--capy-text2);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.card-foot { display: flex; gap: 6px; margin-top: 10px; }
.cap-row { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
.cap-tag {
  font-size: 11px; line-height: 1;
  padding: 4px 7px; border-radius: 999px;
  background: var(--capy-primary-soft); color: var(--capy-primary);
  border: 1px solid var(--capy-primary-border);
}
.tag-icon { width: 13px; height: 13px; border-radius: 3px; object-fit: cover; vertical-align: -2px; margin-right: 3px; }
</style>
