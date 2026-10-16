<template>
  <div class="app-shell">
    <!-- 左：导航轨 -->
    <nav class="nav-rail">
      <div class="rail-logo" title="噜噜 · 佛系桌面助手"><img src="/lulu/1.png" alt="噜噜" class="rail-logo-img" /></div>
      <div class="rail-items">
        <button
          v-for="n in navs" :key="n.name"
          class="rail-item" :class="{ active: route.name === n.name }"
          :title="n.label"
          @click="router.push({ name: n.name })"
        >
          <img class="rail-icon" :src="n.icon" :alt="n.label" />
          <span class="rail-label">{{ n.label }}</span>
        </button>
      </div>
      <div class="rail-sign" title="不许人间见白头">
        <img class="rail-sign-img" src="/lulu/3.png" alt="署名" />
        <span class="rail-sign-text">不许人间见白头</span>
      </div>
      <div class="rail-foot" :title="schedulerText">
        <span class="status-dot" :class="{ on: schedulerRunning }"></span>
      </div>
    </nav>

    <!-- 中：平台状态面板（对话页由 ChatView 自带会话列表） -->
    <aside v-if="route.name !== 'chat'" class="side-panel">
      <div class="lulu-logo-card">
        <div class="lulu-avatar"><img src="/lulu/1.png" alt="噜噜" /></div>
        <div>
          <div class="lulu-name">噜噜</div>
          <div class="lulu-slogan">佛系桌面助手，随缘干活</div>
        </div>
      </div>

      <div class="side-actions">
        <button class="btn btn-primary btn-block btn-mascot" @click="callMascot">
          <img src="/lulu/3.png" alt="噜噜" class="btn-mascot-img" /> 召唤桌宠
        </button>
      </div>

      <div class="capy-section side-stat">
        <div class="stat-row">
          <span>调度器</span>
          <span class="badge" :class="schedulerRunning ? 'badge-ok' : 'badge-off'">
            {{ schedulerRunning ? '运行中' : '已停止' }}
          </span>
        </div>
        <div class="stat-row">
          <span>模型</span>
          <span class="badge" :class="llmReady ? 'badge-ok' : 'badge-danger'">
            {{ llmReady ? '就绪' : '未配置' }}
          </span>
        </div>
        <div class="stat-row">
          <span>配色</span>
          <select class="input palette-sel" :value="palette" @change="switchPalette($event)">
            <option v-for="p in palettes" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>
      </div>

      <div class="capy-section side-tip">
        <div class="tip-title"><img class="tip-icon" src="/lulu/3.png" alt="噜噜" /> 噜噜小记</div>
        <div class="tip-text">{{ tip }}</div>
      </div>
    </aside>

    <!-- 右：主内容 -->
    <main class="main-area">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { miscApi, settingsApi } from '../api'

const route = useRoute()
const router = useRouter()

const navs = [
  { name: 'chat', label: '对话', icon: '/capy/capy02.png' },
  { name: 'team', label: '管家团队', icon: '/capy/capy06.png' },
  { name: 'abilities', label: '技能能力', icon: '/capy/capy08.png' },
  { name: 'tasks', label: '自动任务', icon: '/capy/capy04.png' },
  { name: 'memory', label: '用户记忆', icon: '/capy/capy05.png' },
  { name: 'kb', label: '知识库', icon: '/capy/capy03.png' },
  { name: 'evolve', label: '自主进化', icon: '/capy/capy01.png' },
  { name: 'im', label: 'IM 通道', icon: '/capy/capy_gif01.gif' },
  { name: 'tools', label: '工具记录', icon: '/capy/capy_gif07.gif' },
  { name: 'settings', label: '模型设置', icon: '/capy/capy07.png' },
]

const schedulerRunning = ref(false)
const llmReady = ref(false)
const palette = ref('琥珀暖暗')
const palettes = ref([])
const schedulerText = ref('调度器')
const tip = ref('今天也是摸鱼的一天，有活喊我，没活我躺平。')

const tips = [
  '今天也是摸鱼的一天，有活喊我，没活我躺平。',
  '噜噜不卷，但你要卷的时候叫我。',
  '事缓则圆，代码不急，先喝口茶。',
  '能自动化的绝不动手，这是我的人生信条。',
]

function applyPalette(name) {
  document.body.dataset.palette = name
  localStorage.setItem('capy-palette', name)
  palette.value = name
}

async function switchPalette(ev) {
  const name = ev.target.value
  try { await settingsApi.palette(name) } catch (e) { /* 本地也生效 */ }
  applyPalette(name)
}

async function callMascot() {
  try {
    const r = await miscApi.mascotStart()
    toast(r.message || (r.ok ? '桌宠已打开' : '启动失败'))
  } catch (e) {
    toast('桌宠启动失败：' + e.message)
  }
}

const savedPalette = localStorage.getItem('capy-palette')
if (savedPalette) applyPalette(savedPalette)

onMounted(async () => {
  tip.value = tips[Math.floor(Math.random() * tips.length)]
  try {
    const st = await miscApi.status()
    schedulerRunning.value = st.scheduler_running
    llmReady.value = st.llm_ready
    schedulerText.value = st.scheduler_status || '调度器'
    palettes.value = ['琥珀暖暗', 'Nord', 'Catppuccin Mocha', 'Tokyo Night', 'Solarized Dark', 'GitHub Light', '暖米浅色']
    applyPalette(st.palette)
  } catch (e) {
    palettes.value = ['琥珀暖暗', 'Nord', 'Catppuccin Mocha', 'Tokyo Night', 'Solarized Dark', 'GitHub Light', '暖米浅色']
  }
})

// 简易全局 toast
import { provideToast } from '../composables/toast'
const toast = provideToast()
</script>

<style scoped>
.app-shell { display: flex; height: 100vh; overflow: hidden; }

.nav-rail {
  width: 72px; flex: 0 0 auto;
  background: var(--capy-glass-sidebar);
  backdrop-filter: blur(14px);
  border-right: 1px solid var(--capy-border-soft);
  display: flex; flex-direction: column; align-items: center;
  padding: 12px 0;
  gap: 6px;
}
.rail-logo {
  width: 46px; height: 46px;
  display: flex; align-items: center; justify-content: center;
  background: var(--capy-grad);
  border-radius: var(--capy-radius-md);
  box-shadow: 0 4px 16px var(--capy-primary-glow);
  margin-bottom: 10px;
  overflow: hidden;
}
.rail-logo-img { width: 100%; height: 100%; object-fit: cover; }
.rail-items { flex: 1; display: flex; flex-direction: column; gap: 4px; width: 100%; align-items: center; }
.rail-item {
  width: 52px; padding: 8px 0;
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  border-radius: var(--capy-radius-md);
  color: var(--capy-text2);
  transition: var(--capy-transition);
}
.rail-item:hover { background: var(--capy-primary-soft2); color: var(--capy-text); }
.rail-item.active { background: var(--capy-primary-soft); color: var(--capy-yellow); box-shadow: inset 0 0 0 1px var(--capy-primary-border); }
.rail-icon { width: 24px; height: 24px; border-radius: 7px; object-fit: cover; }
.rail-label { font-size: 10px; }
.rail-foot { padding: 8px; }
.rail-sign {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  width: 52px; padding: 6px 2px; margin-bottom: 2px;
  border-radius: var(--capy-radius-md);
  background: var(--capy-primary-soft2);
  border: 1px solid var(--capy-primary-border);
  cursor: default;
}
.rail-sign-img { width: 18px; height: 18px; border-radius: 50%; object-fit: cover; }
.rail-sign-text {
  writing-mode: vertical-rl;
  font-size: 10px; line-height: 1.5; letter-spacing: 2px;
  color: var(--capy-text2);
}
.status-dot { display: block; width: 10px; height: 10px; border-radius: 50%; background: var(--capy-text2); opacity: .6; }
.status-dot.on { background: var(--capy-ok); opacity: 1; box-shadow: 0 0 8px var(--capy-ok); }

.side-panel {
  width: 240px; flex: 0 0 auto;
  background: var(--capy-glass-sidebar);
  backdrop-filter: blur(14px);
  border-right: 1px solid var(--capy-border-soft);
  padding: 16px 12px;
  display: flex; flex-direction: column; gap: 14px;
  overflow-y: auto;
}
.lulu-logo-card { display: flex; align-items: center; gap: 10px; padding: 6px 4px; }
.lulu-avatar {
  width: 44px; height: 44px; flex: 0 0 auto;
  display: flex; align-items: center; justify-content: center;
  background: var(--capy-primary-soft);
  border: 1px solid var(--capy-primary-border);
  border-radius: var(--capy-radius-md);
  overflow: hidden;
}
.lulu-avatar img { width: 100%; height: 100%; object-fit: cover; }
.lulu-name { font-weight: 700; font-size: 16px; }
.lulu-slogan { font-size: 11px; color: var(--capy-text2); }
.side-actions .btn-block { width: 100%; }
.btn-mascot { display: flex; align-items: center; justify-content: center; gap: 6px; }
.btn-mascot-img { width: 18px; height: 18px; border-radius: 50%; object-fit: cover; }
.side-stat { display: flex; flex-direction: column; gap: 10px; }
.stat-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 13px; }
.palette-sel { width: 118px; padding: 4px 26px 4px 8px; font-size: 12px; }
.side-tip .tip-title { font-weight: 700; margin-bottom: 6px; }
.tip-icon { width: 16px; height: 16px; border-radius: 4px; object-fit: cover; vertical-align: -3px; margin-right: 4px; }
.side-tip .tip-text { font-size: 12px; color: var(--capy-text2); }

.main-area { flex: 1; min-width: 0; overflow-y: auto; }
</style>
