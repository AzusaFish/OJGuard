import { defineStore } from 'pinia'

import { api } from '@/api'
import type { IncidentContext, IncidentType, IncidentWorkspace } from '@/types'

interface IncidentState {
  incidents: IncidentContext[]
  workspace: IncidentWorkspace | null
  loading: boolean
  error: string
}

export const useIncidentsStore = defineStore('incidents', {
  state: (): IncidentState => ({ incidents: [], workspace: null, loading: false, error: '' }),
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
    async loadWorkspace(incidentId: string) {
      this.loading = true
      this.error = ''
      try {
        this.workspace = await api.get<IncidentWorkspace>(`/incidents/${incidentId}/workspace`)
      } catch (error) {
        this.workspace = null
        this.error = error instanceof Error ? error.message : '事故工作台加载失败'
      } finally {
        this.loading = false
      }
    },
    async prepareDemo(type: IncidentType) {
      const workspace = await api.post<IncidentWorkspace>(`/incidents/demo/${type}`)
      this.workspace = workspace
      await this.loadIncidents()
      return workspace
    },
    async approve(incidentId: string, action: string, roleContext: string, actor: string, reason: string) {
      await api.post(`/incidents/${incidentId}/approvals`, {
        action,
        role_context: roleContext,
        actor,
        decision: 'APPROVED',
        reason,
      })
      await this.loadWorkspace(incidentId)
    },
    async operate(incidentId: string, operation: 'control-canary' | 'bulk' | 'verify' | 'close') {
      const path = operation === 'control-canary' || operation === 'bulk'
        ? `/incidents/${incidentId}/execute/${operation}`
        : `/incidents/${incidentId}/${operation}`
      this.workspace = await api.post<IncidentWorkspace>(path)
      return this.workspace
    },
  },
})
