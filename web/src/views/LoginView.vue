<template>
  <div class="login-page">
    <div class="login-card capy-panel">
      <div class="login-brand">
        <div class="login-logo"><img src="/images/lulu/1.png" alt="噜噜" /></div>
        <div class="login-title">噜噜 · 佛系桌面助手</div>
        <div class="login-sub">登录更有归属感，随缘干活也有记忆锚点</div>
      </div>

      <div class="login-tabs">
        <button class="tab" :class="{ active: tab === 'login' }" @click="switchTab('login')">登录</button>
        <button class="tab" :class="{ active: tab === 'register' }" @click="switchTab('register')">注册</button>
      </div>

      <div class="field">
        <label>用户名</label>
        <input v-model.trim="name" class="input" placeholder="请输入用户名" @keyup.enter="submit" />
      </div>
      <div class="field">
        <label>密码</label>
        <input v-model="password" class="input" type="password" placeholder="请输入密码" @keyup.enter="submit" />
      </div>

      <p v-if="error" class="login-error">{{ error }}</p>

      <button class="btn btn-primary btn-block" :disabled="busy" @click="submit">
        {{ busy ? '处理中…' : tab === 'login' ? '登 录' : '注 册' }}
      </button>
      <button class="btn btn-ghost btn-sm login-back" @click="goBack">返回首页</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '../api'

const router = useRouter()

const TOKEN_KEY = 'capy-token'
const REDIRECT_KEY = 'capy-redirect'

const tab = ref('login')
const name = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

function switchTab(t) {
  tab.value = t
  error.value = ''
}

async function submit() {
  error.value = ''
  if (!name.value) { error.value = '请输入用户名'; return }
  if (!password.value) { error.value = '请输入密码'; return }
  busy.value = true
  try {
    let r
    if (tab.value === 'login') {
      r = await authApi.login(name.value, password.value)
    } else {
      await authApi.register(name.value, password.value)
      r = await authApi.login(name.value, password.value)
    }
    localStorage.setItem(TOKEN_KEY, r.token)
    const redirect = localStorage.getItem(REDIRECT_KEY) || '/'
    localStorage.removeItem(REDIRECT_KEY)
    router.replace(redirect)
  } catch (e) {
    error.value = e.message || '操作失败，请重试'
  } finally {
    busy.value = false
  }
}

function goBack() {
  router.replace('/')
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background:
    radial-gradient(1200px 600px at 20% -10%, var(--capy-primary-soft), transparent 60%),
    radial-gradient(900px 500px at 90% 110%, var(--capy-primary-soft2), transparent 55%),
    var(--capy-bg);
}
.login-card {
  width: 380px; max-width: calc(100vw - 32px);
  padding: 28px 28px 20px;
  display: flex; flex-direction: column; gap: 14px;
}
.login-brand { text-align: center; margin-bottom: 4px; }
.login-logo {
  width: 64px; height: 64px; margin: 0 auto 10px;
  display: flex; align-items: center; justify-content: center;
  background: var(--capy-grad);
  border-radius: var(--capy-radius-lg);
  box-shadow: 0 6px 24px var(--capy-primary-glow);
  overflow: hidden;
}
.login-logo img { width: 100%; height: 100%; object-fit: cover; }
.login-title { font-size: 20px; font-weight: 700; }
.login-sub { font-size: 12px; color: var(--capy-text2); margin-top: 2px; }
.login-tabs {
  display: flex; gap: 6px;
  background: var(--capy-card2);
  border: 1px solid var(--capy-border-soft);
  border-radius: var(--capy-radius-pill);
  padding: 4px;
}
.login-tabs .tab {
  flex: 1; padding: 6px 0;
  border-radius: var(--capy-radius-pill);
  color: var(--capy-text2);
  font-weight: 600;
  transition: var(--capy-transition);
}
.login-tabs .tab.active {
  background: var(--capy-grad);
  color: #2B2722;
  box-shadow: 0 2px 10px var(--capy-primary-glow);
}
.login-error { color: var(--capy-danger); font-size: 13px; margin: 0; }
.btn-block { width: 100%; }
.login-back { align-self: center; margin-top: 2px; }
</style>
