import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '@/api'
import type { Approval, AgentEvent, Evidence, Finding, PatchCandidate, RunBundle, RunContext } from '@/types'

export const useRunsStore = defineStore('runs', () => {
  const runs = ref<RunContext[]>([])
  const current = ref<RunContext | null>(null)
  const findings = ref<Finding[]>([])
  const evidence = ref<Evidence[]>([])
  const events = ref<AgentEvent[]>([])
  const patches = ref<PatchCandidate[]>([])
  const approvals = ref<Approval[]>([])
  const loading = ref(false)
  const error = ref('')

  const blockedCount = computed(() => runs.value.filter((item) => item.stage === 'BLOCKED').length)

  async function loadRuns() {
    runs.value = await api.get<RunContext[]>('/runs')
  }

  async function loadRun(runId: string) {
    loading.value = true
    error.value = ''
    try {
      const [context, findingRows, evidenceRows, eventRows, patchRows, approvalRows] = await Promise.all([
        api.get<RunContext>(`/runs/${runId}`),
        api.get<Finding[]>(`/runs/${runId}/findings`),
        api.get<Evidence[]>(`/runs/${runId}/evidence`),
        api.get<AgentEvent[]>(`/runs/${runId}/events`),
        api.get<PatchCandidate[]>(`/runs/${runId}/patches`),
        api.get<Approval[]>(`/runs/${runId}/approvals`),
      ])
      current.value = context
      findings.value = findingRows
      evidence.value = evidenceRows
      events.value = eventRows
      patches.value = patchRows
      approvals.value = approvalRows
      return { context, findings: findingRows, evidence: evidenceRows, events: eventRows, patches: patchRows, approvals: approvalRows } satisfies RunBundle
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '加载失败'
      throw cause
    } finally {
      loading.value = false
    }
  }

  return { runs, current, findings, evidence, events, patches, approvals, loading, error, blockedCount, loadRuns, loadRun }
})
