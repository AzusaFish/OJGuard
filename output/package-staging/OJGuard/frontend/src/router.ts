import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('@/views/DashboardView.vue'), meta: { title: '事故总览' } },
    { path: '/incidents', component: () => import('@/views/IncidentsView.vue'), meta: { title: '事故列表' } },
    { path: '/incidents/:incidentId', component: () => import('@/views/IncidentDetailView.vue'), meta: { title: '事故工作台' } },
    { path: '/approvals', component: () => import('@/views/ApprovalsView.vue'), meta: { title: '审批与重评' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
