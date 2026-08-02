<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { api } from '@/api'
import EmptyState from '@/components/EmptyState.vue'
import StagePill from '@/components/StagePill.vue'
import { useRunsStore } from '@/stores/runs'
import type { Evidence } from '@/types'

const route = useRoute()
const store = useRunsStore()
const runId = computed(() => String(route.params.runId))
const tab = ref('findings')
const evidenceOpen = ref(false)
const evidencePreview = ref<any>(null)
const proposing = ref(false)

onMounted(() => store.loadRun(runId.value))

async function preview(item: Evidence) {
  evidenceOpen.value = true
  evidencePreview.value = null
  try { evidencePreview.value = await api.get(`/runs/${runId.value}/evidence/${encodeURIComponent(item.id)}/content`) }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '证据读取失败') }
}

async function proposePatch() {
  proposing.value = true
  try {
    await api.post(`/workflow/demo/runs/${runId.value}/patches`)
    await store.loadRun(runId.value)
    tab.value = 'patches'
    ElMessage.success('候选 Diff 已生成，尚未修改任何文件')
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '候选补丁生成失败') }
  finally { proposing.value = false }
}
</script>

<template><section class="page" v-loading="store.loading"><div v-if="store.current" class="page-head"><div><span class="mono accent">{{ store.current.run_id }}</span><h2>{{ store.current.package_id }}</h2><p>创建于 {{ new Date(store.current.created_at).toLocaleString() }} · 最后更新 {{ new Date(store.current.updated_at).toLocaleString() }}</p></div><div class="button-row"><StagePill :stage="store.current.stage" /><button v-if="store.current.stage==='BLOCKED' && !store.patches.length" class="primary-button" :disabled="proposing" @click="proposePatch">生成候选修复</button><button class="ghost-button" @click="store.loadRun(runId)">刷新</button></div></div>
  <template v-if="store.current"><div class="metric-grid"><article class="panel metric"><small>确认 Finding</small><strong>{{ store.findings.length }}</strong><em>规则与执行证据关联</em></article><article class="panel metric"><small>Evidence</small><strong>{{ store.evidence.length }}</strong><em>可校验 SHA-256</em></article><article class="panel metric"><small>Agent Events</small><strong>{{ store.events.length }}</strong><em>JSONL 可重放轨迹</em></article><article class="panel metric"><small>审批记录</small><strong>{{ store.approvals.length }}</strong><em>{{ store.current.approval_state }}</em></article></div>
    <article class="panel"><el-tabs v-model="tab">
      <el-tab-pane label="Findings" name="findings"><div v-if="store.findings.length" class="finding-list"><div v-for="item in store.findings" :key="item.id" class="finding-card"><div class="finding-head"><span class="severity" :class="item.severity">{{ item.severity }}</span><span class="mono muted">{{ item.confidence_class }}</span></div><h3>{{ item.category }}</h3><p>{{ item.description }}</p><div class="finding-foot"><span>{{ item.source_agent }}</span><span>{{ item.evidence_ids.join(', ') }}</span></div></div></div><EmptyState v-else title="暂无 Finding" /></el-tab-pane>
      <el-tab-pane label="Evidence" name="evidence"><div v-if="store.evidence.length" class="data-list"><button v-for="item in store.evidence" :key="item.id" class="data-row evidence-row" @click="preview(item)"><div><strong>{{ item.type }}</strong><small>{{ item.id }}</small></div><small>{{ item.producer }} · {{ item.sha256.slice(0,12) }}…</small><span class="accent">查看 →</span></button></div><EmptyState v-else title="暂无证据" /></el-tab-pane>
      <el-tab-pane label="Agent Trace" name="trace"><div v-if="store.events.length" class="timeline"><div v-for="event in store.events" :key="event.id"><i></i><time>{{ new Date(event.created_at).toLocaleTimeString() }}</time><b>{{ event.agent }}</b><span>{{ event.summary }}</span><small>{{ event.event_type }}</small></div></div><EmptyState v-else title="暂无协作事件" /></el-tab-pane>
      <el-tab-pane label="候选补丁" name="patches"><div v-for="patch in store.patches" :key="patch.id" class="patch-card"><div class="panel-title"><h3>{{ patch.title }}</h3><StagePill :stage="patch.status" /></div><p>{{ patch.rationale }}</p><div class="diffs"><details v-for="change in patch.changes" :key="change.relative_path"><summary>{{ change.relative_path }}</summary><pre class="code-block">{{ change.unified_diff }}</pre></details></div><RouterLink class="primary-button" to="/approvals">前往审批中心</RouterLink></div><EmptyState v-if="!store.patches.length" title="还没有候选补丁" description="候选生成只产生 Diff，不修改原始题包。" /></el-tab-pane>
    </el-tabs></article>
  </template><EmptyState v-else-if="!store.loading" title="运行不存在" :description="store.error" />
  <el-dialog v-model="evidenceOpen" title="证据内容" width="min(820px, 92vw)"><pre class="code-block preview">{{ evidencePreview ? JSON.stringify(evidencePreview, null, 2) : '加载中…' }}</pre></el-dialog>
</section></template>

<style scoped>
.finding-list { display:grid; grid-template-columns:repeat(2,1fr); gap:12px; }.finding-card { padding:17px; border:1px solid var(--line); border-radius:13px; background:rgba(255,255,255,.018); }.finding-head,.finding-foot { display:flex; justify-content:space-between; gap:12px; }.finding-head .muted { font-size:9px; }.finding-card h3 { margin:15px 0 8px; font-size:14px; }.finding-card p { margin:0; color:#aec0c8; font-size:12px; line-height:1.6; }.finding-foot { margin-top:16px; color:var(--muted); font:9px 'DM Mono'; overflow-wrap:anywhere; }.evidence-row { width:100%; border:0; color:inherit; text-align:left; cursor:pointer; }.timeline { padding-left:8px; }.timeline>div { display:grid; grid-template-columns:70px 170px 1fr auto; gap:14px; position:relative; padding:0 0 24px 22px; border-left:1px solid var(--line); }.timeline i { position:absolute; left:-4px; top:5px; width:7px; height:7px; border-radius:50%; background:var(--mint); }.timeline time,.timeline small { font:9px 'DM Mono'; color:var(--muted); }.timeline b,.timeline span { font-size:11px; }.patch-card p { color:var(--muted); font-size:12px; }.diffs { display:grid; gap:8px; margin:18px 0; }.diffs summary { cursor:pointer; padding:10px; font:11px 'DM Mono'; color:var(--mint); }.preview { max-height:60vh; } @media(max-width:800px){.finding-list{grid-template-columns:1fr}.timeline>div{grid-template-columns:1fr;gap:4px}}
</style>
