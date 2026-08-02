export type RunStage =
  | 'RECEIVED'
  | 'BASELINE_VALIDATING'
  | 'ANALYZING'
  | 'TESTING'
  | 'EVIDENCE_REVIEW'
  | 'BLOCKED'
  | 'HUMAN_REVIEW_REQUIRED'
  | 'PASS_CANDIDATE'
  | 'PATCH_PENDING_APPROVAL'
  | 'REVALIDATING'
  | 'READY_FOR_RELEASE'
  | 'FAILED'
  | 'CANCELLED'
  | 'BUDGET_EXHAUSTED'

export interface RunContext {
  task_id: string
  package_id: string
  run_id: string
  stage: RunStage
  active_hypothesis_ids: string[]
  confirmed_finding_ids: string[]
  evidence_ids: string[]
  approval_state: string
  budgets: { test_cases: number; execution_seconds: number; llm_calls: number }
  created_at: string
  updated_at: string
}

export interface Finding {
  id: string
  category: string
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical'
  confidence_class: string
  description: string
  source_agent: string
  evidence_ids: string[]
  replay_action?: string
}

export interface Evidence {
  id: string
  type: string
  producer: string
  artifact_path: string
  sha256: string
  inputs: string[]
  outputs: string[]
  created_at: string
}

export interface AgentEvent {
  id: string
  agent: string
  event_type: string
  summary: string
  artifact_ids: string[]
  matrix_room_id?: string
  created_at: string
}

export interface PatchChange {
  relative_path: string
  before_sha256?: string
  after_sha256: string
  unified_diff: string
}

export interface PatchCandidate {
  id: string
  run_id: string
  title: string
  rationale: string
  risk: string
  status: string
  finding_ids: string[]
  regression_scope: string[]
  changes: PatchChange[]
}

export interface Approval {
  id: string
  action: string
  state: string
  actor: string
  target_id: string
  reason?: string
  created_at: string
}

export interface RunBundle {
  context: RunContext
  findings: Finding[]
  evidence: Evidence[]
  events: AgentEvent[]
  patches: PatchCandidate[]
  approvals: Approval[]
}

export interface BenchmarkReport {
  scope: string
  case_count: number
  defect_count: number
  metrics: Record<string, number>
  cases: Array<{
    package_id: string
    clean_package: boolean
    expected: string[]
    observed: string[]
    matched: boolean
    duration_ms: number
  }>
}
