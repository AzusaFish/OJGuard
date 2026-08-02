<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { api } from '@/api'
import EmptyState from '@/components/EmptyState.vue'
import StagePill from '@/components/StagePill.vue'
import type { PatchCandidate, RunContext } from '@/types'

interface PatchWithRun extends PatchCandidate { run?: RunContext }
const rows = ref<PatchWithRun[]>([])
const loading = ref(false)
const loadError = ref('')
const actor = ref(localStorage.getItem('ojguard.actor') || 'local-reviewer')

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const runs = await api.get<RunContext[]>('/runs')
    const groups = await Promise.all(runs.map(async (run) => (await api.get<PatchCandidate[]>(`/runs/${run.run_id}/patches`)).map((patch) => ({ ...patch, run }))))
    rows.value = groups.flat().reverse()
  } catch (error) {
    rows.value = []
    loadError.value = error instanceof Error ? error.message : '无法连接 OJGuard 后端'
  } finally { loading.value = false }
}

async function reason(title: string) {
  localStorage.setItem('ojguard.actor', actor.value)
  const result = await ElMessageBox.prompt('请记录本次决定的理由', title, { inputPlaceholder: '审阅证据与 Diff 后的判断', confirmButtonText: '确认', cancelButtonText: '取消' })
  return result.value
}

async function approve(patch: PatchWithRun) {
  try { const why = await reason('第一次审批：应用到工作副本'); await api.post(`/workflow/demo/patches/${patch.id}/approve`, { actor: actor.value, reason: why }); ElMessage.success('已应用到隔离工作副本，原题包未改变'); await load() } catch (error:any) { if (error !== 'cancel') ElMessage.error(error?.message || '审批未完成') }
}
async function reject(patch: PatchWithRun) {
  try { const why = await reason('拒绝候选补丁'); await api.post(`/workflow/demo/patches/${patch.id}/reject`, { actor: actor.value, reason: why }); ElMessage.success('已拒绝，未修改文件'); await load() } catch (error:any) { if (error !== 'cancel') ElMessage.error(error?.message || '拒绝未完成') }
}
async function regress(patch: PatchWithRun) {
  try { const result:any = await api.post(`/workflow/demo/patches/${patch.id}/regression`); result.passed ? ElMessage.success('全部回归通过，仍需二次确认') : ElMessage.error('回归失败，发布继续阻断'); await load() } catch (error) { ElMessage.error(error instanceof Error ? error.message : '回归失败') }
}
async function confirm(patch: PatchWithRun) {
  try { const why = await reason('第二次审批：确认发布候选'); await api.post(`/workflow/demo/patches/${patch.id}/confirm`, { actor: actor.value, reason: why }); ElMessage.success('已确认为可发布候选；系统未连接真实 OJ 发布'); await load() } catch (error:any) { if (error !== 'cancel') ElMessage.error(error?.message || '确认未完成') }
}
onMounted(load)
</script>

<template><section class="page" v-loading="loading"><div class="page-head"><div><h2>Agent 建议，人类决定。</h2><p>第一次批准只允许写入独立工作副本；回归通过后，第二次确认才将状态推进到 READY_FOR_RELEASE。</p></div><el-input v-model="actor" placeholder="审批人标识" style="max-width:240px" /></div>
  <div class="approval-flow"><span>候选 Diff</span><i>→</i><span>人工审批 1</span><i>→</i><span>工作副本</span><i>→</i><span>完整回归</span><i>→</i><span>人工审批 2</span></div>
    <div v-if="rows.length" class="approval-list"><article v-for="patch in rows" :key="patch.id" class="panel"><div class="panel-title"><div><span class="mono accent">{{ patch.id }}</span><h3>{{ patch.title }}</h3></div><StagePill :stage="patch.run?.stage==='READY_FOR_RELEASE' ? 'READY_FOR_RELEASE' : patch.status" /></div><p>{{ patch.rationale }}</p><div class="patch-meta"><span>风险 {{ patch.risk }}</span><span>{{ patch.changes.length }} 个文件</span><span>{{ patch.finding_ids.length }} 个 Finding</span></div><div class="button-row"><button v-if="patch.status==='CANDIDATE'" class="primary-button" @click="approve(patch)">审阅并批准应用</button><button v-if="patch.status==='CANDIDATE'" class="danger-button" @click="reject(patch)">拒绝</button><button v-if="patch.status==='APPLIED'" class="primary-button" @click="regress(patch)">执行完整回归</button><button v-if="patch.status==='REGRESSION_PASSED' && patch.run?.stage!=='READY_FOR_RELEASE'" class="primary-button" @click="confirm(patch)">二次确认发布候选</button><RouterLink class="ghost-button" :to="`/runs/${patch.run_id}`">查看证据与 Diff</RouterLink></div></article></div><EmptyState v-else :title="loadError ? '暂时无法读取审批' : '暂无待处理补丁'" :description="loadError || '从 BLOCKED 的主 Demo 运行中生成候选修复。'" />
</section></template>

<style scoped>.approval-flow { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:18px; }.approval-flow span { padding:9px 12px; border:1px solid var(--line); border-radius:9px; color:#b7c7ce; font-size:11px; }.approval-flow i { color:var(--mint); font-style:normal; }.approval-list { display:grid; gap:14px; }.panel-title>div h3 { margin:8px 0 0; }.panel>p { color:var(--muted); font-size:12px; line-height:1.6; }.patch-meta { display:flex; gap:18px; margin:16px 0; color:var(--muted); font:10px 'DM Mono'; }</style>
