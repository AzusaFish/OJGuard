import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('@/views/DashboardView.vue'), meta: { title: '总览' } },
    { path: '/demo', component: () => import('@/views/DemoView.vue'), meta: { title: '主 Demo' } },
    { path: '/packages', component: () => import('@/views/UploadView.vue'), meta: { title: '题包接入' } },
    { path: '/runs', component: () => import('@/views/RunsView.vue'), meta: { title: '审计任务' } },
    { path: '/runs/:runId', component: () => import('@/views/RunDetailView.vue'), meta: { title: '运行详情' } },
    { path: '/approvals', component: () => import('@/views/ApprovalsView.vue'), meta: { title: '审批中心' } },
    { path: '/benchmark', component: () => import('@/views/BenchmarkView.vue'), meta: { title: '基准评测' } },
    { path: '/architecture', component: () => import('@/views/ArchitectureView.vue'), meta: { title: '协作架构' } },
    { path: '/settings', component: () => import('@/views/SettingsView.vue'), meta: { title: '系统设置' } },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
