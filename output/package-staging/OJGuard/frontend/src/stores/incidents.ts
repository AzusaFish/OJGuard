import { defineStore } from 'pinia'

import { api } from '@/api'
import type {
  AgentRunEvent,
  AgentRunSnapshot,
  AgentTeamsRuntimeStatus,
  IncidentContext,
  IncidentType,
  IncidentWorkspace,
} from '@/types'

interface IncidentState {
  incidents: IncidentContext[]
  workspace: IncidentWorkspace | null
  agentRun: AgentRunSnapshot | null
  agentEvents: AgentRunEvent[]
  agentRuntime: AgentTeamsRuntimeStatus | null
  loading: boolean
  error: string
}

export const useIncidentsStore = defineStore('incidents', {
  state: (): IncidentState => ({
    incidents: [],
    workspace: null,
    agentRun: null,
    agentEvents: [],
    agentRuntime: null,
    loading: false,
    error: '',
  }),
  actions: {
    async loadIncidents() {
      this.loading = true
      this.error = ''
      try {
        this.incidents = await api.get<IncidentContext[]>('/incidents')
      } catch (error) {
        this.error = error instanceof Error ? error.message : '事故列表加载失败'
      } finally {
        this.loading = false
      }
    },
    async loadWorkspace(incidentId: string, silent = false) {
      if (!silent) this.loading = true
      this.error = ''
      try {
        this.workspace = await api.get<IncidentWorkspace>(`/incidents/${incidentId}/workspace`)
      } catch (error) {
        this.workspace = null
        this.error = error instanceof Error ? error.message : '事故工作台加载失败'
      } finally {
        if (!silent) this.loading = false
      }
    },
    async startAgentIncident(type: IncidentType) {
      const snapshot = await api.post<AgentRunSnapshot>('/agent-runs', {
        incident_type: type,
        max_model_responses: 20,
      })
      this.agentRun = snapshot
      this.agentEvents = []
      this.agentRuntime = null
      await this.loadIncidents()
      return snapshot
    },
    async loadAgentRun(incidentId: string) {
      const runs = await api.get<AgentRunSnapshot['run'][]>(`/agent-runs?incident_id=${encodeURIComponent(incidentId)}`)
      if (!runs.length) {
        this.agentRun = null
        this.agentEvents = []
        this.agentRuntime = null
        return null
      }
      const runId = runs[0].run_id
      this.agentRun = await api.get<AgentRunSnapshot>(`/agent-runs/${runId}`)
      this.agentEvents = await api.get<AgentRunEvent[]>(`/agent-runs/${runId}/events`)
      this.agentRuntime = await api.get<AgentTeamsRuntimeStatus>(`/agent-runs/${runId}/runtime`)
      return this.agentRun
    },
    async refreshAgentRun() {
      if (!this.agentRun) return null
      const runId = this.agentRun.run.run_id
      const after = this.agentEvents.at(-1)?.sequence || 0
      const [snapshot, events] = await Promise.all([
        api.get<AgentRunSnapshot>(`/agent-runs/${runId}`),
        api.get<AgentRunEvent[]>(`/agent-runs/${runId}/events?after_sequence=${after}`),
      ])
      this.agentRun = snapshot
      if (events.length) this.agentEvents.push(...events)
      return snapshot
    },
    async launchAgentRun(actor: string) {
      if (!this.agentRun) throw new Error('当前事故没有 AgentRun')
      await api.post(`/agent-runs/${this.agentRun.run.run_id}/launch`, {
        approval_actor: actor,
        timeout_minutes: 20,
      })
      return this.refreshAgentRun()
    },
    async resumeAgentRun(actor: string) {
      if (!this.agentRun) throw new Error('当前事故没有 AgentRun')
      await api.post(`/agent-runs/${this.agentRun.run.run_id}/resume`, {
        approval_actor: actor,
        timeout_minutes: 20,
      })
      return this.refreshAgentRun()
    },
    async approve(incidentId: string, action: string, roleContext: string, actor: string, reason: string) {
      return this.decideApproval(incidentId, action, roleContext, actor, reason, 'APPROVED')
    },
    async decideApproval(incidentId: string, action: string, roleContext: string, actor: string, reason: string, decision: 'APPROVED' | 'REJECTED') {
      await api.post(`/incidents/${incidentId}/approvals`, {
        action,
        role_context: roleContext,
        actor,
        decision,
        reason,
      })
      await this.loadWorkspace(incidentId)
      await this.refreshAgentRun()
    },
  },
})
