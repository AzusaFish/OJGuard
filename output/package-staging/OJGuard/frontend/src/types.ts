export type IncidentType =
  | 'runtime_regression'
  | 'node_degradation'
  | 'checker_defect'
  | 'queue_congestion'
  | 'configuration_drift'

export type IncidentStage =
  | 'DETECTED'
  | 'TRIAGING'
  | 'INVESTIGATING'
  | 'IMPACT_ASSESSING'
  | 'REMEDIATION_PLANNING'
  | 'APPROVAL_PENDING'
  | 'EXECUTING'
  | 'REJUDGING'
  | 'VERIFYING'
  | 'RESOLVED'
  | 'HUMAN_REVIEW_REQUIRED'
  | 'PAUSED'
  | 'ROLLED_BACK'
  | 'FAILED'

export interface IncidentProfile {
  incident_type: IncidentType
  title: string
  summary: string
  severity: 'SEV1' | 'SEV2' | 'SEV3' | 'SEV4'
  playbook_id: string
  resource_scope: Record<string, unknown>
  source_systems: string[]
  dimensions: string[]
}

export interface IncidentContext {
  incident_id: string
  profile: IncidentProfile
  stage: IncidentStage
  signal_ids: string[]
  active_hypothesis_ids: string[]
  confirmed_root_cause_ids: string[]
  experiment_ids: string[]
  impact_assessment_id?: string
  remediation_plan_ids: string[]
  approval_state: Record<string, string>
  rejudge_batch_ids: string[]
  score_change_ids: string[]
  verification_id?: string
  evidence_ids: string[]
  open_questions: string[]
  control_experiment_passed: boolean
  canary_rejudge_passed: boolean
  rejudge_complete: boolean
  created_at: string
  updated_at: string
}

export interface IncidentSignal {
  id: string
  kind: string
  source: string
  observed_at: string
  summary: string
  dimensions: Record<string, string | number | boolean | null>
  evidence_ids: string[]
}

export interface RootCauseHypothesis {
  id: string
  category: string
  statement: string
  confidence: number
  state: string
  evidence_ids: string[]
}

export interface IncidentExperiment {
  id: string
  kind: string
  title: string
  state: string
  conclusion?: string
  metrics: Record<string, string | number | boolean | null>
  evidence_ids: string[]
}

export interface ImpactAssessment {
  id: string
  policy: string
  candidate_ids: string[]
  submission_ids: string[]
  problem_ids: string[]
  languages: string[]
  affected_candidate_count: number
  affected_submission_count: number
  projected_score_change_count: number
  projected_advancement_change_count: number
}

export interface RemediationStep {
  id: string
  action: string
  risk_level: string
  preconditions: string[]
  success_checks: string[]
  stop_conditions: string[]
  rollback_action: string
}

export interface RemediationPlan {
  id: string
  title: string
  approved_impact_id: string
  steps: RemediationStep[]
}

export interface IncidentApproval {
  id: string
  action: string
  level: string
  decision: string
  role_context: string
  actor: string
  target_id: string
  reason?: string
  decided_at?: string
}

export interface RejudgeBatch {
  id: string
  sequence: number
  kind: 'control' | 'canary' | 'bulk' | string
  idempotency_key: string
  submission_ids: string[]
  state: string
  planned_count: number
  completed_count: number
  failed_count: number
  skipped_count: number
}

export interface ScoreChange {
  id: string
  candidate_id: string
  before_score: number
  after_score: number
  before_rank?: number
  after_rank?: number
  advancement_changed: boolean
}

export interface IncidentVerification {
  id: string
  status: string
  checks: Record<string, boolean>
  coverage_rate: number
  duplicate_rejudge_count: number
  missing_rejudge_count: number
  cross_scope_regression_count: number
  summary: string
}

export interface DiagnosticPlaybook {
  id: string
  display_name: string
  incident_type: IncidentType
  signal_dimensions: string[]
  experiment_kinds: string[]
  impact_policy: string
  verification_checks: string[]
}

export interface IncidentWorkspace {
  incident: IncidentContext
  playbook: DiagnosticPlaybook
  signals: IncidentSignal[]
  hypotheses: RootCauseHypothesis[]
  experiments: IncidentExperiment[]
  impacts: ImpactAssessment[]
  remediation_plans: RemediationPlan[]
  approvals: IncidentApproval[]
  rejudge_batches: RejudgeBatch[]
  score_changes: ScoreChange[]
  verifications: IncidentVerification[]
}
