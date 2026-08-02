<script setup lang="ts">
import { computed, onMounted } from 'vue'

import EmptyState from '@/components/EmptyState.vue'
import StagePill from '@/components/StagePill.vue'
import { useIncidentsStore } from '@/stores/incidents'

const store = useIncidentsStore()
const latest = computed(() => store.incidents.slice(0, 6))
const active = computed(() => store.incidents.filter((item) => !['RESOLVED', 'FAILED', 'ROLLED_BACK'].includes(item.stage)).length)
const waiting = computed(() => store.incidents.filter((item) => item.stage === 'APPROVAL_PENDING').length)
const rejudging = computed(() => store.incidents.filter((item) => ['EXECUTING', 'REJUDGING', 'VERIFYING'].includes(item.stage)).length)
const resolved = computed(() => store.incidents.filter((item) => item.stage === 'RESOLVED').length)
const priority = computed(() =>
  store.incidents.find((item) => ['APPROVAL_PENDING', 'HUMAN_REVIEW_REQUIRED', 'REJUDGING'].includes(item.stage))
  || latest.value.find((item) => !['RESOLVED', 'CLOSED'].includes(item.stage))
  || latest.value[0],
)

onMounted(() => store.loadIncidents())
</script>

<template>
  <section class="page" v-loading="store.loading">
    <div class="page-head">
      <div><span class="section-kicker">运行概况</span><h2>在线测评事故总览</h2><p>集中查看异常研判、审批、分批重评和闭环验证状态。</p></div>
      <RouterLink class="primary-button" to="/incidents">新建事故演练</RouterLink>
    </div>

    <div class="metric-grid">
      <article class="panel metric"><small>处理中</small><strong>{{ active }}</strong><em>尚未进入终态的事故</em></article>
      <article class="panel metric"><small>等待审批</small><strong class="warning-text">{{ waiting }}</strong><em>需要明确的人工作业</em></article>
      <article class="panel metric"><small>重评与验证</small><strong>{{ rejudging }}</strong><em>控制、灰度或全量批次</em></article>
      <article class="panel metric"><small>已闭环</small><strong class="success-text">{{ resolved }}</strong><em>验证通过并完成关闭</em></article>
    </div>

    <div class="two-column">
      <article class="panel priority-card">
        <div class="panel-title"><h3>当前优先事项</h3><span>按待审批与重评状态优先</span></div>
        <template v-if="priority">
          <div class="priority-head"><div><span class="incident-id">{{ priority.incident_id }}</span><h3>{{ priority.profile.title }}</h3></div><StagePill :stage="priority.stage" /></div>
          <p>{{ priority.profile.summary }}</p>
          <div class="fact-row"><span>{{ priority.profile.severity }}</span><span>{{ priority.profile.playbook_id }}</span><span>{{ new Date(priority.updated_at).toLocaleString() }}</span></div>
          <RouterLink class="primary-button" :to="`/incidents/${priority.incident_id}`">进入事故工作台</RouterLink>
        </template>
        <EmptyState v-else title="暂无事故" description="从事故列表启动一个可复现演练。" />
      </article>

      <aside class="panel flow-card">
        <div class="panel-title"><h3>闭环路径</h3></div>
        <ol>
          <li><b>01</b><span>聚合信号<small>异常、部署、投诉</small></span></li>
          <li><b>02</b><span>确认根因<small>竞争假设与对照实验</small></span></li>
          <li><b>03</b><span>冻结影响面<small>提交、选手、成绩与排名</small></span></li>
          <li><b>04</b><span>审批后重评<small>控制组、灰度、全量</small></span></li>
          <li><b>05</b><span>独立验证<small>覆盖、重复、越界与一致性</small></span></li>
        </ol>
      </aside>
    </div>

    <article class="panel recent-panel">
      <div class="panel-title"><h3>最近事故</h3><RouterLink to="/incidents">查看全部 →</RouterLink></div>
      <div v-if="latest.length" class="data-list">
        <RouterLink v-for="incident in latest" :key="incident.incident_id" class="data-row" :to="`/incidents/${incident.incident_id}`">
          <div><strong>{{ incident.profile.title }}</strong><small>{{ incident.incident_id }}</small></div>
          <div><strong>{{ incident.profile.severity }} · {{ incident.profile.incident_type }}</strong><small>{{ new Date(incident.updated_at).toLocaleString() }}</small></div>
          <StagePill :stage="incident.stage" />
        </RouterLink>
      </div>
      <EmptyState v-else title="暂无事故记录" description="启动一个演练后，信号、审批、重评和验证状态会显示在这里。" />
    </article>
  </section>
</template>

<style scoped>
.priority-card p{color:var(--muted);line-height:1.7}.priority-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.priority-head h3{font-size:22px;margin:8px 0}.fact-row{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}.fact-row span{padding:7px 9px;border-radius:8px;background:var(--panel-soft);color:var(--muted);font-size:11px}.flow-card ol{list-style:none;margin:0;padding:0;display:grid;gap:3px}.flow-card li{display:flex;gap:14px;padding:13px 0;border-bottom:1px solid var(--line-soft)}.flow-card li:last-child{border:0}.flow-card b{color:var(--accent);font:700 11px var(--mono)}.flow-card span{font-size:13px;font-weight:700}.flow-card small{display:block;margin-top:4px;color:var(--muted);font-weight:400}.recent-panel{margin-top:18px}
</style>
