<script setup lang="ts">
import { computed, onMounted } from 'vue'

import EmptyState from '@/components/EmptyState.vue'
import StagePill from '@/components/StagePill.vue'
import { useIncidentsStore } from '@/stores/incidents'
import type { IncidentContext } from '@/types'

const store = useIncidentsStore()
const relevant = computed(() => store.incidents.filter((item) =>
  ['APPROVAL_PENDING', 'EXECUTING', 'REJUDGING', 'VERIFYING', 'HUMAN_REVIEW_REQUIRED', 'PAUSED'].includes(item.stage),
))

function pendingFor(item: IncidentContext) {
  if (item.stage === 'APPROVAL_PENDING' && item.approval_state.execute_plan !== 'APPROVED') return '技术审批：处置方案'
  if (item.stage === 'APPROVAL_PENDING' && item.approval_state.run_canary_rejudge !== 'APPROVED') return '技术审批：控制组与灰度'
  if (!item.canary_rejudge_passed) return '执行控制组与灰度'
  if (item.approval_state.run_bulk_rejudge !== 'APPROVED') return '业务审批：全量重评'
  if (!item.rejudge_complete) return '执行全量重评'
  if (!item.verification_id) return '独立闭环验证'
  if (item.approval_state.close_incident !== 'APPROVED') return '业务审批：关闭事故'
  return '完成事故关闭'
}

onMounted(() => store.loadIncidents())
</script>

<template>
  <section class="page" v-loading="store.loading">
    <div class="page-head"><div><span class="section-kicker">人工工作队列</span><h2>审批与重评</h2><p>集中呈现需要操作者做决定或执行的事故，明确下一步动作与责任角色。</p></div></div>
    <div class="role-note"><div><b>技术审批</b><span>确认根因证据、影响集合、停止条件与控制/灰度方案。</span></div><div><b>业务审批</b><span>确认全量重评范围、结果影响与事故关闭。</span></div><p>单人演示会把两类决定分别记录为角色上下文，完整保留操作者和时间。</p></div>
    <div v-if="relevant.length" class="queue-list">
      <article v-for="incident in relevant" :key="incident.incident_id" class="panel queue-card">
        <div><span class="incident-id">{{ incident.incident_id }}</span><h3>{{ incident.profile.title }}</h3><p>{{ incident.profile.summary }}</p></div>
        <div class="queue-state"><StagePill :stage="incident.stage" /><small>当前待办</small><strong>{{ pendingFor(incident) }}</strong><RouterLink class="primary-button" :to="`/incidents/${incident.incident_id}`">进入处理</RouterLink></div>
      </article>
    </div>
    <EmptyState v-else title="当前没有待审批或待执行事故" description="新演练进入 APPROVAL_PENDING 后会自动出现在这里。" />
  </section>
</template>

<style scoped>
.role-note{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:18px}.role-note>div{padding:14px 16px;background:white;border:1px solid var(--line);border-radius:10px}.role-note b,.role-note span{display:block}.role-note b{color:var(--accent)}.role-note span{margin-top:5px;color:var(--muted);font-size:12px}.role-note p{grid-column:1/-1;margin:0;color:var(--muted);font-size:11px}.queue-list{display:grid;gap:12px}.queue-card{display:grid;grid-template-columns:1fr 260px;gap:24px;align-items:center;border-left:4px solid var(--accent)}.queue-card h3{font-size:19px;margin:8px 0}.queue-card p{margin:0;color:var(--muted)}.queue-state{display:grid;gap:8px;justify-items:start}.queue-state small{margin-top:7px;color:var(--muted)}.queue-state strong{font-size:14px}.queue-state .primary-button{margin-top:8px}@media(max-width:760px){.role-note,.queue-card{grid-template-columns:1fr}.role-note p{grid-column:1}}
</style>
