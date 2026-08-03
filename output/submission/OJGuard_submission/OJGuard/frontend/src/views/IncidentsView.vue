<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import StagePill from '@/components/StagePill.vue'
import { useIncidentsStore } from '@/stores/incidents'
import type { IncidentType } from '@/types'

const store = useIncidentsStore()
const router = useRouter()
const search = ref('')
const stage = ref('all')
const starting = ref<IncidentType | ''>('')
const executable = [
  { type: 'runtime_regression' as IncidentType, name: 'Java 运行时回归', detail: '镜像变更后 Java 提交超时率异常上升', tag: '核心场景 · 20,000 提交' },
  { type: 'node_degradation' as IncidentType, name: '评测节点退化', detail: '单个评测节点出现集中运行错误', tag: '泛化验证 · 3,000 提交' },
  { type: 'checker_defect' as IncidentType, name: 'Checker 缺陷', detail: 'Checker 版本变更导致判定结果漂移', tag: '泛化验证 · 1,600 提交' },
]
const contractOnly = ['评测队列拥塞', '评测配置漂移']
const filtered = computed(() => store.incidents.filter((item) => {
  const matchesStage = stage.value === 'all' || item.stage === stage.value
  const needle = search.value.trim().toLowerCase()
  const matchesSearch = !needle || `${item.incident_id} ${item.profile.title} ${item.profile.incident_type}`.toLowerCase().includes(needle)
  return matchesStage && matchesSearch
}))

async function start(type: IncidentType) {
  starting.value = type
  try {
    const snapshot = await store.startAgentIncident(type)
    ElMessage.success('原始事故信号已创建，等待启动 AgentTeams 协同处置')
    await router.push(`/incidents/${snapshot.incident.incident_id}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '演练启动失败')
  } finally {
    starting.value = ''
  }
}

onMounted(() => store.loadIncidents())
</script>

<template>
  <section class="page" v-loading="store.loading">
    <div class="page-head"><div><span class="section-kicker">事故入口</span><h2>创建事故或继续协同处置</h2><p>创建后只保留原始信号，由 AgentTeams 的 Incident Manager 拆解任务并调度专业 Worker。</p></div></div>
    <div class="scenario-grid">
      <article v-for="item in executable" :key="item.type" class="panel scenario-card">
        <span>{{ item.tag }}</span><h3>{{ item.name }}</h3><p>{{ item.detail }}</p>
        <button class="primary-button" :disabled="Boolean(starting)" @click="start(item.type)">{{ starting === item.type ? '正在创建…' : '创建事故' }}</button>
      </article>
    </div>
    <div class="contract-note"><b>已预留流程类型</b><span v-for="item in contractOnly" :key="item">{{ item }}</span><small>待接入真实适配器后启用</small></div>

    <article class="panel incident-list-panel">
      <div class="list-toolbar"><div><h3>全部事故</h3><small>{{ filtered.length }} 条记录</small></div><div class="filters"><input v-model="search" placeholder="搜索事故编号或标题"><select v-model="stage"><option value="all">全部状态</option><option value="APPROVAL_PENDING">等待审批</option><option value="EXECUTING">处置执行</option><option value="REJUDGING">可信重评</option><option value="VERIFYING">闭环验证</option><option value="RESOLVED">已解决</option><option value="HUMAN_REVIEW_REQUIRED">人工复核</option></select></div></div>
      <div v-if="filtered.length" class="data-list">
        <RouterLink v-for="incident in filtered" :key="incident.incident_id" class="data-row" :to="`/incidents/${incident.incident_id}`">
          <div><strong>{{ incident.profile.title }}</strong><small>{{ incident.incident_id }} · {{ incident.profile.playbook_id }}</small></div>
          <div><strong>{{ incident.profile.severity }}</strong><small>更新于 {{ new Date(incident.updated_at).toLocaleString() }}</small></div>
          <StagePill :stage="incident.stage" />
        </RouterLink>
      </div>
      <EmptyState v-else title="没有匹配的事故" description="调整筛选条件，或启动一个可复现演练。" />
    </article>
  </section>
</template>

<style scoped>
.scenario-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.scenario-card{border-top:3px solid var(--accent)}.scenario-card>span{color:var(--accent);font-size:11px;font-weight:800}.scenario-card h3{font-size:19px;margin:13px 0 8px}.scenario-card p{min-height:48px;color:var(--muted);line-height:1.6;font-size:13px}.contract-note{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:14px 0 24px;padding:12px 15px;background:#fff8ed;border:1px solid #f2ddbc;border-radius:10px;font-size:12px}.contract-note span{padding:5px 8px;background:white;border:1px solid #ead7bb;border-radius:7px}.contract-note small{color:var(--muted)}.incident-list-panel{padding:0;overflow:hidden}.list-toolbar{padding:20px 22px;display:flex;justify-content:space-between;gap:20px;align-items:center;border-bottom:1px solid var(--line-soft)}.list-toolbar h3{margin:0}.list-toolbar small{color:var(--muted)}.filters{display:flex;gap:8px}.filters input,.filters select{border:1px solid var(--line);border-radius:8px;padding:9px 11px;background:white;color:var(--text)}.incident-list-panel .data-list{border-radius:0}.incident-list-panel .data-row{background:white}@media(max-width:900px){.scenario-grid{grid-template-columns:1fr}.list-toolbar{align-items:stretch;flex-direction:column}.filters{flex-direction:column}}
</style>
