<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { api } from '@/api'

const route = useRoute()
const menuOpen = ref(false)
const online = ref(false)
const nav = [
  { path: '/', label: '总览', code: '01' },
  { path: '/demo', label: '主 Demo', code: '02' },
  { path: '/packages', label: '题包接入', code: '03' },
  { path: '/runs', label: '审计任务', code: '04' },
  { path: '/approvals', label: '审批中心', code: '05' },
  { path: '/benchmark', label: '基准评测', code: '06' },
  { path: '/architecture', label: '协作架构', code: '07' },
  { path: '/settings', label: '系统设置', code: '08' },
]
const title = computed(() => String(route.meta.title || 'OJGuard'))

onMounted(async () => {
  try {
    await api.get('/health')
    online.value = true
  } catch {
    online.value = false
  }
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ open: menuOpen }">
      <RouterLink class="brand" to="/" @click="menuOpen = false">
        <span class="brand-mark"><i></i><i></i><i></i></span>
        <span><b>OJGuard</b><small>Evidence before release</small></span>
      </RouterLink>
      <nav class="navigation">
        <RouterLink v-for="item in nav" :key="item.path" :to="item.path" @click="menuOpen = false">
          <span class="nav-code">{{ item.code }}</span><span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-foot">
        <span class="status-dot" :class="{ online }"></span>
        <div><strong>{{ online ? '核心服务在线' : '等待后端连接' }}</strong><small>Local · single user</small></div>
      </div>
    </aside>
    <main class="main-area">
      <header class="topbar">
        <button class="menu-button" aria-label="打开菜单" @click="menuOpen = !menuOpen">☰</button>
        <div><span class="eyebrow">OJ 内容发布防线</span><h1>{{ title }}</h1></div>
        <div class="topbar-meta"><span>DeepSeek</span><b>Mock-safe</b></div>
      </header>
      <RouterView />
    </main>
    <button v-if="menuOpen" class="mobile-scrim" aria-label="关闭菜单" @click="menuOpen = false"></button>
  </div>
</template>
