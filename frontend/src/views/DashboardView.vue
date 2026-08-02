<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api'
import EmptyState from '@/components/EmptyState.vue'
import StagePill from '@/components/StagePill.vue'
import { useRunsStore } from '@/stores/runs'
import type { BenchmarkReport } from '@/types'

const store = useRunsStore()
const benchmark = ref<BenchmarkReport | null>(null)
const system = ref<Record<string, any> | null>(null)
const latest = computed(() => store.runs.slice(0, 5))
const ready = computed(() => store.runs.filter((item) => item.stage === 'READY_FOR_RELEASE').length)
const evidenceCount = computed(() => store.runs.reduce((sum, item) => sum + item.evidence_ids.length, 0))

onMounted(async () => {
  const [report, info] = await Promise.allSettled([
    api.get<BenchmarkReport>('/benchmark/report'),
    api.get<Record<string, any>>('/system'),
    store.loadRuns(),
  ])
  if (report.status === 'fulfilled') benchmark.value = report.value
  if (info.status === 'fulfilled') system.value = info.value
})
</script>

<template>
  <section class="page">
    <div class="page-head">
      <div><h2>让证据先于发布。</h2><p>OJGuard 把题面、程序、测试与 Checker 的风险判断转成可复现执行证据，并在关键修改前后保留人工控制权。</p></div>
      <RouterLink class="primary-button" to="/demo">运行主 Demo</RouterLink>
    </div>
    <div class="metric-grid">
      <article class="panel metric"><small>审计运行</small><strong>{{ store.runs.length }}</strong><em>SQLite 持久化任务</em></article>
      <article class="panel metric"><small>当前阻断</small><strong class="danger-text">{{ store.blockedCount }}</strong><em>等待修复或人工处置</em></article>
      <article class="panel metric"><small>证据索引</small><strong>{{ evidenceCount }}</strong><em>含 SHA-256 完整性</em></article>
      <article class="panel metric"><small>可发布候选</small><strong class="accent">{{ ready }}</strong><em>均需二次确认</em></article>
    </div>
    <div class="two-column">
      <article class="panel">
        <div class="panel-title"><h3>最近运行</h3><RouterLink to="/runs">查看全部 →</RouterLink></div>
        <div v-if="latest.length" class="data-list">
          <RouterLink v-for="run in latest" :key="run.run_id" class="data-row" :to="`/runs/${run.run_id}`">
            <div><strong>{{ run.package_id }}</strong><small>{{ run.run_id }}</small></div>
            <small>{{ new Date(run.updated_at).toLocaleString() }}</small><StagePill :stage="run.stage" />
          </RouterLink>
        </div>
        <EmptyState v-else title="还没有审计运行" description="从主 Demo 或题包接入开始。" />
      </article>
      <aside class="panel">
        <div class="panel-title"><h3>工程实况</h3><span>LIVE CONTRACT</span></div>
        <div class="signal-list">
          <div><span>确定性 benchmark</span><b>{{ benchmark ? `${(benchmark.metrics.recall * 100).toFixed(0)}% recall` : '未生成' }}</b></div>
          <div><span>模型调用</span><b>{{ system?.llm_calls_enabled ? '已启用' : '默认关闭' }}</b></div>
          <div><span>RAG 端口</span><b>{{ system?.rag?.port || 8010 }} · 预留</b></div>
          <div><span>AgentTeams</span><b>{{ system?.agentteams?.version || 'v1.2.0' }}</b></div>
        </div>
        <div class="guard-note"><i>!</i><p><strong>安全边界</strong>Agent 不持有密钥、不直接访问 Docker，也不能批准补丁或发布。</p></div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.signal-list { display: grid; gap: 2px; }.signal-list div { display: flex; justify-content: space-between; padding: 13px 0; border-bottom: 1px solid var(--line-soft); font-size: 12px; }.signal-list span { color: var(--muted); }.signal-list b { font: 11px 'DM Mono'; color: var(--mint); }.guard-note { display: flex; gap: 11px; margin-top: 20px; padding: 14px; background: rgba(255,191,105,.07); border: 1px solid rgba(255,191,105,.15); border-radius: 12px; }.guard-note i { color: var(--amber); font-style: normal; font-weight: 800; }.guard-note p { margin: 0; color: var(--muted); font-size: 11px; line-height: 1.6; }.guard-note strong { display: block; color: var(--text); margin-bottom: 3px; }
</style>
