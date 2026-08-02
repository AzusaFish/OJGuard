<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { api } from '@/api'

const route = useRoute()
const menuOpen = ref(false)
const online = ref(false)
const nav = [
  { path: '/', label: '事故总览', code: '01' },
  { path: '/incidents', label: '事故列表', code: '02' },
  { path: '/approvals', label: '审批与重评', code: '03' },
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
        <span class="brand-mark">OJ</span>
        <span><b>OJGuard</b><small>测评事故响应与可信重评</small></span>
      </RouterLink>
      <nav class="navigation">
        <RouterLink v-for="item in nav" :key="item.path" :to="item.path" @click="menuOpen = false">
          <span class="nav-code">{{ item.code }}</span><span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-foot">
        <span class="status-dot" :class="{ online }"></span>
        <div><strong>{{ online ? '服务正常' : '服务未连接' }}</strong><small>{{ online ? '事故工作台可用' : '请先启动后端' }}</small></div>
      </div>
    </aside>
    <main class="main-area">
      <header class="topbar">
        <button class="menu-button" aria-label="打开菜单" @click="menuOpen = !menuOpen">☰</button>
        <div><span class="eyebrow">ONLINE JUDGE OPERATIONS</span><h1>{{ title }}</h1></div>
        <RouterLink class="topbar-action" to="/incidents">新建事故演练</RouterLink>
      </header>
      <RouterView />
    </main>
    <button v-if="menuOpen" class="mobile-scrim" aria-label="关闭菜单" @click="menuOpen = false"></button>
  </div>
</template>
