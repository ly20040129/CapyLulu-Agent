const BASE = '/api'

async function http(method, url, body) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(BASE + url, opts)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch (e) { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  get: (url) => http('GET', url),
  post: (url, body) => http('POST', url, body ?? {}),
  put: (url, body) => http('PUT', url, body ?? {}),
  patch: (url, body) => http('PATCH', url, body ?? {}),
  del: (url) => http('DELETE', url),
}

export const chatApi = {
  status: () => api.get('/chat/status'),
  sessions: () => api.get('/chat/sessions'),
  createSession: () => api.post('/chat/sessions'),
  getSession: (id) => api.get(`/chat/sessions/${encodeURIComponent(id)}`),
  rename: (id, title) => api.post(`/chat/sessions/${encodeURIComponent(id)}/rename`, { title }),
  del: (id) => api.del(`/chat/sessions/${encodeURIComponent(id)}`),
  send: (sessionId, text, specialist) => api.post('/chat/send', { session_id: sessionId, text, specialist }),
}

export const teamApi = {
  agents: () => api.get('/team/agents'),
  add: (body) => api.post('/team/agents', body),
  update: (name, body) => api.put(`/team/agents/${encodeURIComponent(name)}`, body),
  toggle: (name, enabled) => api.patch(`/team/agents/${encodeURIComponent(name)}/enabled`, { enabled }),
  del: (name) => api.del(`/team/agents/${encodeURIComponent(name)}`),
  tasks: () => api.get('/team/tasks'),
  dispatchTest: (body) => api.post('/team/tasks', body),
  clearTasks: () => api.post('/team/tasks/clear'),
}

export const skillsApi = {
  list: () => api.get('/skills'),
  add: (body) => api.post('/skills', body),
  del: (name) => api.del(`/skills/${encodeURIComponent(name)}`),
  files: () => api.get('/skills/files'),
  createSkill: (body) => api.post('/skills/create', body),
}

export const mcpApi = {
  list: () => api.get('/mcp/servers'),
  add: (body) => api.post('/mcp/servers', body),
  update: (name, body) => api.put(`/mcp/servers/${encodeURIComponent(name)}`, body),
  toggle: (name, enabled) => api.patch(`/mcp/servers/${encodeURIComponent(name)}/enabled`, { enabled }),
  test: (name) => api.post(`/mcp/servers/${encodeURIComponent(name)}/test`),
  tools: (name) => api.get(`/mcp/servers/${encodeURIComponent(name)}/tools`),
  del: (name) => api.del(`/mcp/servers/${encodeURIComponent(name)}`),
  market: (q = '') => api.get(`/mcp/market${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  installMarket: (name) => api.post('/mcp/market/install', { name }),
  dynamic: () => api.get('/mcp/dynamic'),
  refresh: () => api.post('/mcp/refresh'),
}

export const tasksApi = {
  list: () => api.get('/tasks'),
  add: (text) => api.post('/tasks', { text }),
  toggle: (text, enabled) => api.patch(`/tasks/${encodeURIComponent(text)}/enabled`, { enabled }),
  del: (text) => api.del(`/tasks/${encodeURIComponent(text)}`),
  logs: () => api.get('/tasks/logs'),
}

export const memoryApi = {
  list: () => api.get('/memories'),
  read: (name) => api.get(`/memories/${encodeURIComponent(name)}`),
  create: (name, content) => api.post('/memories', { name, content }),
  save: (name, content) => api.put(`/memories/${encodeURIComponent(name)}`, { name, content }),
  del: (name) => api.del(`/memories/${encodeURIComponent(name)}`),
  tiers: () => api.get('/memories/tiers'),
  lastDream: () => api.get('/memories/last-dream'),
  logWorking: (session, content) => api.post('/memories/tiers/working', { session, content }),
  logEpisodic: (body) => api.post('/memories/tiers/episodic', body),
  deepDream: (force = false, limit = 50) => api.post('/memories/deep-dream', { force, limit }),
  query: (q, limit = 10) => api.get(`/memories/query?q=${encodeURIComponent(q)}&limit=${limit}`),
}

export const kbApi = {
  list: () => api.get('/kb'),
  create: (name) => api.post('/kb', { name }),
  del: (name) => api.del(`/kb/${encodeURIComponent(name)}`),
  docs: (name) => api.get(`/kb/${encodeURIComponent(name)}/docs`),
  addDoc: (name, body) => api.post(`/kb/${encodeURIComponent(name)}/docs`, body),
  delDoc: (name, docId) => api.del(`/kb/${encodeURIComponent(name)}/docs/${encodeURIComponent(docId)}`),
  search: (q, kb = '', topK = 5) => api.get(`/kb/search?q=${encodeURIComponent(q)}&kb=${encodeURIComponent(kb)}&top_k=${topK}`),
  ask: (body) => api.post('/kb/ask', body),
}

export const toolsApi = {
  logs: (n = 240) => api.get(`/tools/logs?n=${n}`),
  clear: () => api.post('/tools/clear'),
}

export const evolveApi = {
  lessons: () => api.get('/evolve/lessons'),
  addLesson: (body) => api.post('/evolve/lessons', body),
  delLesson: (id) => api.del(`/evolve/lessons/${encodeURIComponent(id)}`),
  reflect: (force = true, limit = 20) => api.post('/evolve/reflect', { force, limit }),
  improve: (force = true, maxAuto = 3) => api.post('/evolve/improve', { force, max_auto: maxAuto }),
  log: () => api.get('/evolve/log'),
  status: () => api.get('/evolve/status'),
}

export const imApi = {
  channels: () => api.get('/im/channels'),
  add: (body) => api.post('/im/channels', body),
  update: (name, body) => api.put(`/im/channels/${encodeURIComponent(name)}`, body),
  del: (name) => api.del(`/im/channels/${encodeURIComponent(name)}`),
  test: (name, text) => api.post(`/im/channels/${encodeURIComponent(name)}/test`, { text }),
  inbox: (limit = 100) => api.get(`/im/inbox?limit=${limit}`),
  clearInbox: () => api.del('/im/inbox'),
  incoming: (channel, text) => api.post('/im/inbox/incoming', { channel, text }),
  poll: () => api.post('/im/poll'),
}

export const settingsApi = {
  get: () => api.get('/settings'),
  llm: (body) => api.post('/settings/llm', body),
  palette: (name) => api.post('/settings/palette', { name }),
}

export const miscApi = {
  status: () => api.get('/status'),
  mascotStart: () => api.post('/mascot/start'),
  schedulerStart: () => api.post('/scheduler/start'),
  schedulerStop: () => api.post('/scheduler/stop'),
}
