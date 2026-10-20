<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2><img class="head-icon" src="/images/lulu/5.png" alt="能力中心" /> 能力中心</h2>
        <div class="sub">接入 MCP 服务（stdio / sse / http），AI 即可调度其工具</div>
      </div>
      <button class="btn btn-primary" @click="showAdd = !showAdd">＋ 添加服务</button>
    </div>

    <div v-if="showAdd" class="capy-panel add-panel">
      <div class="row-fields">
        <div class="field">
          <label>服务名</label>
          <input v-model="form.name" class="input" placeholder="如：file-system / weather" />
        </div>
        <div class="field">
          <label>连接类型</label>
          <select v-model="form.type" class="input">
            <option value="stdio">stdio（本地命令）</option>
            <option value="sse">sse（SSE 远程）</option>
            <option value="http">http（Streamable HTTP）</option>
          </select>
        </div>
      </div>
      <div class="field">
        <label>配置（JSON）</label>
        <textarea v-model="form.config" class="input mono" rows="4"
          placeholder='stdio: {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "D:/"]}&#10;sse/http: {"url": "http://host:port/mcp"}'></textarea>
      </div>
      <div class="field field-check">
        <label class="check"><input type="checkbox" v-model="form.enabled" /> 添加后立即启用</label>
      </div>
      <div class="detail-actions">
        <button class="btn btn-secondary" @click="showAdd = false">取消</button>
        <button class="btn btn-primary" @click="addServer">保存</button>
      </div>
    </div>

    <div class="capy-panel market-panel">
      <div class="panel-title-row">
        <div class="panel-title">MCP 市场 <span class="panel-sub">内置常见服务，一键安装并自动注册工具</span></div>
        <div class="market-search">
          <input v-model="marketQ" class="input" placeholder="搜索服务（名称 / 关键字），留空显示全部" @keyup.enter="loadMarket" />
          <button class="btn btn-secondary btn-sm" @click="loadMarket">搜索</button>
          <button class="btn btn-ghost btn-sm" @click="refreshDynamic" title="按已接入并启用的服务重刷动态注册">刷新注册</button>
        </div>
      </div>
      <div v-if="marketLoading" class="muted">搜索中…</div>
      <div v-else class="market-grid">
        <div v-for="m in marketItems" :key="m.name" class="market-item">
          <div class="market-name">{{ m.display }} <span class="mono">[{{ m.name }}]</span></div>
          <div class="market-desc">{{ m.desc }}</div>
          <div class="market-foot">
            <span class="badge badge-yellow">{{ m.type }}</span>
            <button class="btn btn-primary btn-sm" :disabled="installed(m.name)" @click="installMarket(m)">
              {{ installed(m.name) ? '已接入' : '安装' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="capy-panel dynamic-panel">
      <div class="panel-title-row">
        <div class="panel-title">动态注册工具 <span class="panel-sub">已启用服务的工具以 mcp_&lt;server&gt;_&lt;tool&gt; 进入主工具表，AI 可直接调用</span></div>
        <span class="badge" :class="dynamicTools.length ? 'badge-green' : 'badge-gray'">{{ dynamicTools.length }} 个</span>
      </div>
      <div v-if="dynamicTools.length" class="dynamic-list">
        <div v-for="t in dynamicTools" :key="t.name" class="dynamic-item">
          <span class="mono tool-name">{{ t.name }}</span>
          <span class="tool-desc">{{ t.description }}</span>
          <span class="badge badge-yellow">{{ t.risk }}</span>
        </div>
      </div>
      <div v-else class="muted">暂无动态注册工具：接入并启用服务、获取工具清单后会自动注册。</div>
    </div>

    <div v-if="!sdkOk" class="capy-panel warn-panel">MCP SDK 未安装：请先执行 <code>pip install mcp</code>，否则无法连接服务。</div>

    <div class="grid-list">
      <div v-for="s in servers" :key="s.name" class="capy-card mcp-card">
        <div class="card-top">
          <div class="mcp-name">{{ s.name }}</div>
          <div class="badges">
            <span class="badge badge-yellow">{{ s.type }}</span>
            <span class="badge" :class="s.enabled ? 'badge-green' : 'badge-gray'">{{ s.enabled ? '已启用' : '已停用' }}</span>
          </div>
        </div>
        <div class="mcp-config mono">{{ configBrief(s) }}</div>
        <div class="mcp-tools" v-if="s.tools_cache && s.tools_cache.length">
          <div class="tools-title">工具（{{ s.tools_cache.length }}）</div>
          <div v-for="t in s.tools_cache.slice(0, 8)" :key="t.name" class="tool-item">
            <span class="tool-name">{{ t.name }}</span>
            <span class="tool-desc">{{ t.description || '——' }}</span>
          </div>
          <div v-if="s.tools_cache.length > 8" class="tools-more">… 还有 {{ s.tools_cache.length - 8 }} 个</div>
        </div>
        <div class="mcp-tools" v-else>
          <div class="tools-title">尚未获取工具清单</div>
        </div>
        <div class="card-foot">
          <div class="foot-left">
            <button class="btn btn-ghost btn-sm" @click="testServer(s)">{{ testing === s.name ? '连接中…' : '测试连接' }}</button>
            <button class="btn btn-ghost btn-sm" @click="toggleServer(s)">{{ s.enabled ? '停用' : '启用' }}</button>
          </div>
          <div class="foot-right">
            <button class="btn btn-ghost btn-icon btn-sm" @click="removeServer(s)" title="删除"><img class="btn-icon-img" src="/images/lulu/7.png" alt="删除" /></button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="!servers.length" class="empty-tip">
      还没有接入任何 MCP 服务。点右上角「添加服务」，填入命令或地址即可接入，例如
      <code>{"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "D:/"]}</code>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { mcpApi } from '../api'
import { toast } from '../composables/toast'

const servers = ref([])
const sdkOk = ref(true)
const showAdd = ref(false)
const testing = ref('')
const form = ref({ name: '', type: 'stdio', config: '', enabled: true })
const marketItems = ref([])
const marketQ = ref('')
const marketLoading = ref(false)
const dynamicTools = ref([])

async function load() {
  try {
    const r = await mcpApi.list()
    servers.value = r.items || []
    sdkOk.value = r.sdk_ok !== false
  } catch (e) { toast('加载失败：' + e.message) }
}

async function addServer() {
  if (!form.value.name.trim()) { toast('服务名不能为空'); return }
  try {
    const r = await mcpApi.add(form.value)
    toast(r.message || '添加成功')
    showAdd.value = false
    form.value = { name: '', type: 'stdio', config: '', enabled: true }
    await load()
  } catch (e) { toast('添加失败：' + e.message) }
}

async function testServer(s) {
  testing.value = s.name
  try {
    const r = await mcpApi.test(s.name)
    toast(r.message || (r.ok ? '连接成功' : '连接失败'))
    await load()
  } catch (e) { toast('测试失败：' + e.message) }
  testing.value = ''
}

async function toggleServer(s) {
  try {
    const r = await mcpApi.toggle(s.name, !s.enabled)
    toast(r.message || '已更新')
    await load()
  } catch (e) { toast('操作失败：' + e.message) }
}

async function removeServer(s) {
  if (!window.confirm(`确定移除 MCP 服务「${s.name}」？`)) return
  try {
    const r = await mcpApi.del(s.name)
    toast(r.message || '已移除')
    await load()
  } catch (e) { toast('删除失败：' + e.message) }
}

function configBrief(s) {
  const c = s.config || {}
  if (s.type === 'stdio') return `$ ${c.command || ''} ${(c.args || []).join(' ')}`.trim()
  return c.url || ''
}

async function loadMarket() {
  marketLoading.value = true
  try {
    const r = await mcpApi.market(marketQ.value.trim())
    marketItems.value = r.items || []
  } catch (e) { toast('市场加载失败：' + e.message) }
  marketLoading.value = false
}

function installed(name) {
  return servers.value.some(s => s.name === name)
}

async function installMarket(m) {
  try {
    const r = await mcpApi.installMarket(m.name)
    toast(r.message || '安装成功')
    await load()
    await loadDynamic()
  } catch (e) { toast(e.message || '安装失败') }
}

async function loadDynamic() {
  try {
    const r = await mcpApi.dynamic()
    dynamicTools.value = r.items || []
  } catch (e) { /* 忽略，页面不因动态工具失败而报错 */ }
}

async function refreshDynamic() {
  try {
    const r = await mcpApi.refresh()
    toast(r.message || '已刷新')
    await loadDynamic()
  } catch (e) { toast('刷新失败：' + e.message) }
}

onMounted(() => {
  load()
  loadMarket()
  loadDynamic()
})
</script>

<style scoped>
.page { padding: 20px 24px; }
.head-icon { width: 22px; height: 22px; border-radius: 6px; object-fit: cover; vertical-align: -4px; margin-right: 6px; }
.btn-icon-img { width: 16px; height: 16px; border-radius: 4px; object-fit: cover; vertical-align: -3px; }
.add-panel { margin-bottom: 16px; padding: 18px 20px; max-width: 720px; }
.warn-panel { margin-bottom: 16px; padding: 12px 16px; border-color: var(--capy-warn, #d97706); }
.warn-panel code { background: rgba(255,255,255,.12); padding: 1px 6px; border-radius: 4px; }
.row-fields { display: flex; gap: 12px; }
.row-fields .field { flex: 1; }
.field-check { margin-top: 10px; }
.check { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.detail-actions { display: flex; gap: 8px; margin-top: 12px; }
.grid-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }
.mcp-card { transition: var(--capy-transition); }
.mcp-card:hover { transform: translateY(-2px); box-shadow: var(--capy-shadow-hover); }
.card-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.mcp-name { font-weight: 700; font-size: 15px; }
.badges { display: flex; gap: 6px; }
.mcp-config { margin-top: 8px; font-size: 12px; color: var(--capy-text2); word-break: break-all; }
.mcp-tools { margin-top: 10px; padding: 8px 10px; background: rgba(255,255,255,.05); border-radius: 8px; }
.tools-title { font-size: 12px; color: var(--capy-text2); margin-bottom: 6px; }
.tool-item { display: flex; gap: 8px; align-items: baseline; font-size: 12px; }
.tool-name { font-weight: 600; white-space: nowrap; }
.tool-desc { color: var(--capy-text2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tools-more { font-size: 12px; color: var(--capy-text2); margin-top: 4px; }
.card-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 12px; }
.foot-left, .foot-right { display: flex; align-items: center; gap: 6px; }
.mono { font-family: Consolas, 'Courier New', monospace; font-size: 12px; }
.badge-green { background: var(--capy-green, #3f9d63); color: #fff; }
.badge-gray { background: rgba(255,255,255,.15); color: var(--capy-text2); }
.empty-tip { color: var(--capy-text2); text-align: center; padding: 40px 0; }
.empty-tip code { background: rgba(255,255,255,.1); padding: 1px 6px; border-radius: 4px; }
.market-panel, .dynamic-panel { margin-bottom: 16px; padding: 16px 18px; }
.panel-title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.panel-title { font-weight: 700; font-size: 15px; }
.panel-sub { font-size: 12px; font-weight: 400; color: var(--capy-text2); margin-left: 6px; }
.market-search { display: flex; gap: 6px; align-items: center; }
.market-search .input { width: 240px; }
.market-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
.market-item { padding: 10px 12px; border: 1px solid rgba(255,255,255,.1); border-radius: 8px; }
.market-name { font-size: 14px; font-weight: 600; }
.market-name .mono { font-size: 12px; color: var(--capy-text2); }
.market-desc { font-size: 12px; color: var(--capy-text2); margin-top: 4px; min-height: 34px; }
.market-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
.dynamic-list { display: flex; flex-direction: column; gap: 6px; }
.dynamic-item { display: flex; align-items: baseline; gap: 8px; font-size: 12px; padding: 6px 8px; background: rgba(255,255,255,.05); border-radius: 6px; }
.dynamic-item .tool-desc { flex: 1; color: var(--capy-text2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.muted { color: var(--capy-text2); font-size: 13px; padding: 8px 0; }
</style>
