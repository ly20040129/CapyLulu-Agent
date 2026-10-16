import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../layout/AppShell.vue'

const routes = [
  {
    path: '/',
    component: AppShell,
    children: [
      { path: '', redirect: '/chat' },
      { path: 'chat', name: 'chat', component: () => import('../views/ChatView.vue'), meta: { title: '对话', icon: '/lulu/4.png' } },
      { path: 'team', name: 'team', component: () => import('../views/TeamView.vue'), meta: { title: '管家团队', icon: '/lulu/2.png' } },
      { path: 'abilities', name: 'abilities', component: () => import('../views/AbilitiesView.vue'), meta: { title: '技能能力', icon: '/capy/capy08.png' } },
      { path: 'skills', redirect: '/abilities' },
      { path: 'mcp', redirect: '/abilities' },
      { path: 'tasks', name: 'tasks', component: () => import('../views/TasksView.vue'), meta: { title: '自动任务', icon: '/lulu/3.png' } },
      { path: 'memory', name: 'memory', component: () => import('../views/MemoryView.vue'), meta: { title: '用户记忆', icon: '/lulu/6.png' } },
      { path: 'kb', name: 'kb', component: () => import('../views/KbView.vue'), meta: { title: '知识库', icon: '/lulu/6.png' } },
      { path: 'evolve', name: 'evolve', component: () => import('../views/EvolveView.vue'), meta: { title: '自主进化', icon: '/lulu/6.png' } },
      { path: 'im', name: 'im', component: () => import('../views/ImView.vue'), meta: { title: 'IM 通道', icon: '/lulu/6.png' } },
      { path: 'tools', name: 'tools', component: () => import('../views/ToolsView.vue'), meta: { title: '工具记录', icon: '/lulu/7.png' } },
      { path: 'settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { title: '模型设置', icon: '/lulu/1.png' } },
    ],
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
