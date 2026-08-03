<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import StagePill from '@/components/StagePill.vue'
import { useIncidentsStore } from '@/stores/incidents'

const route = useRoute()
const store = useIncidentsStore()
const tab = ref('agents')
const actor = ref(localStorage.getItem('ojguard.incident.actor') || 'demo-operator')
const busy = ref(false)
const incidentId = computed(() => String(route.params.incidentId))
const workspace = computed(() => store.workspace)
const incident = computed(() => workspace.value?.incident)
const agentRun = computed(() => store.agentRun?.run)
const legalOptions = computed(() => store.agentRun?.legal_options || [])
const agentEvents = computed(() => store.agentEvents)
const runtime = computed(() => store.agentRuntime)
const impact = computed(() => workspace.value?.impacts.at(-1))
const plan = computed(() => workspace.value?.remediation_plans.at(-1))
const experiment = computed(() => workspace.value?.experiments.at(-1))
const verification = computed(() => workspace.value?.verifications.at(-1))
const approval = (key: string) => incident.value?.approval_state[key] === 'APPROVED'
const stages = [
  ['DETECTED', '发现'], ['TRIAGING', '研判'], ['INVESTIGATING', '根因'],
  ['IMPACT_ASSESSING', '影响'], ['REMEDIATION_PLANNING', '处置'], ['APPROVAL_PENDING', '审批'],
  ['EXECUTING', '执行'], ['REJUDGING', '重评'], ['VERIFYING', '验证'], ['RESOLVED', '关闭'],
]
const currentIndex = computed(() => stages.findIndex(([value]) => value === incident.value?.stage))
const completedBatches = computed(() => workspace.value?.rejudge_batches.filter((item) => item.state === 'COMPLETED').length || 0)
const nextAction = computed(() => {
  if (!incident.value) return '加载事故状态'
  if (!agentRun.value) return '为事故创建 AgentRun'
  if (agentRun.value.status === 'QUEUED') return '启动 AgentTeams 协同处置'
  if (agentRun.value.status === 'STARTING') return 'AgentTeams 运行环境正在接管事故'
  if (agentRun.value.status === 'FAILED') return `AgentTeams 运行失败：${agentRun.value.failure_reason || '等待人工处理'}`
  if (agentRun.value.status === 'PAUSED') return `AgentTeams 已暂停：${agentRun.value.failure_reason || '等待恢复'}`
  if (['TRIAGING', 'INVESTIGATING', 'IMPACT_ASSESSING', 'REMEDIATION_PLANNING'].includes(incident.value.stage)) {
    return `${agentRun.value.current_agent || 'Incident Manager'} 正在处理 ${agentRun.value.current_action || '协同任务'}`
  }
  if (incident.value.stage === 'APPROVAL_PENDING' && !approval('execute_plan')) return '技术角色审批处置方案'
  if (incident.value.stage === 'APPROVAL_PENDING' && !approval('run_canary_rejudge')) return '技术角色审批控制组与灰度重评'
  if (!incident.value.canary_rejudge_passed) return '执行控制组与灰度重评'
  if (!approval('run_bulk_rejudge')) return '业务角色审批全量重评'
  if (!incident.value.rejudge_complete) return '执行受影响提交全量重评'
  if (!verification.value) return '执行独立闭环验证'
  if (!approval('close_incident')) return '业务角色确认事故关闭'
  if (incident.value.stage !== 'RESOLVED') return '关闭事故'
  return '事故已完成闭环'
})

let refreshTimer: number | undefined
let eventSource: EventSource | undefined
const agentEventTypes = [
  'RUN_CREATED', 'RUN_STARTED', 'ROUTE_DECISION', 'WORKER_STARTED', 'WORKER_RESULT',
  'TOOL_RESULT', 'STATE_TRANSITION', 'HUMAN_GATE', 'RUN_PAUSED', 'RUN_RESUMED',
  'FINAL_REPORT', 'ERROR',
]

function connectAgentStream() {
  eventSource?.close()
  if (!store.agentRun) return
  const runId = store.agentRun.run.run_id
  const after = store.agentEvents.at(-1)?.sequence || 0
  eventSource = new EventSource(`/api/v1/agent-runs/${runId}/stream?after_sequence=${after}`)
  const onAgentEvent: EventListener = async (rawEvent) => {
    const message = rawEvent as MessageEvent<string>
    const event = JSON.parse(message.data)
    if (!store.agentEvents.some((item) => item.id === event.id)) store.agentEvents.push(event)
    await Promise.all([store.refreshAgentRun(), store.loadWorkspace(incidentId.value, true)])
  }
  for (const eventType of agentEventTypes) eventSource.addEventListener(eventType, onAgentEvent)
}

async function launchAgentTeams() {
  if (!runtime.value?.ready) {
    ElMessage.warning(runtime.value?.message || 'AgentTeams 运行环境尚未就绪')
    return
  }
  try {
    await ElMessageBox.confirm(
      `启动后将调用 DeepSeek，最多接受 ${agentRun.value?.max_model_responses || 20} 条模型响应；遇到审批门禁时会等待你的操作。`,
      '启动 AgentTeams',
      { confirmButtonText: '确认启动', cancelButtonText: '取消', type: 'warning' },
    )
    busy.value = true
    localStorage.setItem('ojguard.incident.actor', actor.value)
    await store.launchAgentRun(actor.value)
    ElMessage.success('AgentTeams 正在启动，协作事件将实时写入工作台')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error instanceof Error ? error.message : 'AgentTeams 启动失败')
  } finally { busy.value = false }
}

async function resumeAgentTeams() {
  if (!runtime.value?.ready) {
    ElMessage.warning(runtime.value?.message || 'AgentTeams 运行环境尚未就绪')
    return
  }
  try {
    await ElMessageBox.confirm('将从已持久化的 IncidentContext 和事件序列恢复协同运行，不会重新创建事故。', '恢复 AgentTeams', {
      confirmButtonText: '确认恢复', cancelButtonText: '取消', type: 'warning',
    })
    busy.value = true
    await store.resumeAgentRun(actor.value)
    ElMessage.success('AgentTeams 正在恢复运行')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error instanceof Error ? error.message : 'AgentTeams 恢复失败')
  } finally { busy.value = false }
}

async function approveAction(action: string, roleContext: string, label: string) {
  try {
    await ElMessageBox.confirm(`将以“${roleContext === 'technical_approver' ? '技术审批' : '业务审批'}”角色记录：${label}。`, '确认审批', {
      confirmButtonText: '记录批准', cancelButtonText: '取消', type: 'warning',
    })
    busy.value = true
    localStorage.setItem('ojguard.incident.actor', actor.value)
    await store.approve(incidentId.value, action, roleContext, actor.value, label)
    ElMessage.success('审批记录已保存')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error instanceof Error ? error.message : '审批未完成')
  } finally { busy.value = false }
}

async function rejectAction(action: string, roleContext: string, label: string) {
  try {
    await ElMessageBox.confirm(`拒绝后 AgentTeams 将停止当前执行并保留全部上下文：${label}。`, '拒绝审批', {
      confirmButtonText: '确认拒绝', cancelButtonText: '取消', type: 'error',
    })
    busy.value = true
    localStorage.setItem('ojguard.incident.actor', actor.value)
    await store.decideApproval(incidentId.value, action, roleContext, actor.value, label, 'REJECTED')
    ElMessage.warning('审批已拒绝，AgentTeams 将进入失败处理')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error instanceof Error ? error.message : '拒绝操作未完成')
  } finally { busy.value = false }
}

function openReport() {
  window.open(`/api/v1/incidents/${incidentId.value}/report.html`, '_blank', 'noopener')
}

async function refresh() {
  await Promise.all([store.loadWorkspace(incidentId.value), store.loadAgentRun(incidentId.value)])
  connectAgentStream()
}
onMounted(() => {
  refresh()
  refreshTimer = window.setInterval(async () => {
    if (!store.agentRun) return
    await Promise.all([store.refreshAgentRun(), store.loadWorkspace(incidentId.value, true)])
  }, 5000)
})
onBeforeUnmount(() => {
  eventSource?.close()
  if (refreshTimer) window.clearInterval(refreshTimer)
})
watch(incidentId, refresh)
</script>

<template>
  <section class="page" v-loading="store.loading || busy">
    <template v-if="workspace && incident">
      <div class="detail-head">
        <div><RouterLink class="back-link" to="/incidents">← 返回事故列表</RouterLink><span class="incident-id">{{ incident.incident_id }}</span><h2>{{ incident.profile.title }}</h2><p>{{ incident.profile.summary }}</p></div>
        <div class="head-actions"><StagePill :stage="incident.stage" /><button class="ghost-button" @click="refresh">刷新</button><button class="primary-button" @click="openReport">查看事故报告</button></div>
      </div>

      <div class="stage-track">
        <div v-for="([value, label], index) in stages" :key="value" :class="{ done: index < currentIndex, active: value === incident.stage }"><i>{{ index < currentIndex ? '✓' : index + 1 }}</i><span>{{ label }}</span></div>
      </div>

      <article class="panel agent-command-bar">
        <div>
          <span class="section-kicker">AgentTeams 控制平面</span>
          <h3>{{ agentRun ? `${agentRun.current_agent || 'Incident Manager'} · ${agentRun.status}` : '尚未创建 AgentRun' }}</h3>
          <p v-if="agentRun">{{ agentRun.current_action || '等待启动' }} · 模型响应 {{ agentRun.model_response_count }}/{{ agentRun.max_model_responses }}</p>
        </div>
        <div class="runtime-state" :class="{ ready: runtime?.ready }">
          <b>{{ runtime?.ready ? '运行环境就绪' : '运行环境未就绪' }}</b>
          <small>{{ runtime?.message || '正在检查 AgentTeams' }}</small>
        </div>
        <button v-if="agentRun?.status === 'QUEUED'" class="primary-button" :disabled="!runtime?.ready" @click="launchAgentTeams">启动 AgentTeams</button>
        <button v-if="agentRun?.status === 'FAILED' || agentRun?.status === 'PAUSED'" class="primary-button" :disabled="!runtime?.ready" @click="resumeAgentTeams">恢复 AgentTeams</button>
      </article>

      <div class="metric-grid detail-metrics">
        <article class="panel metric"><small>受影响提交</small><strong>{{ impact?.affected_submission_count ?? '—' }}</strong><em>{{ impact?.affected_candidate_count ?? 0 }} 名选手</em></article>
        <article class="panel metric"><small>对照实验</small><strong class="status-word">{{ experiment?.state ?? '待执行' }}</strong><em>{{ experiment?.kind || '尚未生成' }}</em></article>
        <article class="panel metric"><small>重评进度</small><strong>{{ completedBatches }}/{{ workspace.rejudge_batches.length }}</strong><em>{{ incident.rejudge_complete ? '批次全部完成' : '控制、灰度、全量分批执行' }}</em></article>
        <article class="panel metric"><small>闭环验证</small><strong class="status-word">{{ verification?.status ?? '待验证' }}</strong><em>{{ verification ? `${(verification.coverage_rate * 100).toFixed(0)}% 覆盖率` : '重评后执行' }}</em></article>
      </div>

      <div class="action-strip">
        <div><small>下一步</small><strong>{{ nextAction }}</strong></div>
        <div class="operator"><label>当前操作者</label><input v-model="actor" aria-label="当前操作者"></div>
        <div class="button-row">
          <button v-if="incident.stage === 'APPROVAL_PENDING' && !approval('execute_plan')" class="primary-button" @click="approveAction('APPROVE_REMEDIATION','technical_approver','批准处置方案')">技术审批：处置方案</button>
          <button v-if="incident.stage === 'APPROVAL_PENDING' && !approval('execute_plan')" class="ghost-button" @click="rejectAction('APPROVE_REMEDIATION','technical_approver','拒绝当前处置方案')">拒绝处置方案</button>
          <button v-if="incident.stage === 'APPROVAL_PENDING' && approval('execute_plan') && !approval('run_canary_rejudge')" class="primary-button" @click="approveAction('RUN_CANARY_REJUDGE','technical_approver','批准控制组与灰度重评')">技术审批：控制与灰度</button>
          <button v-if="incident.stage === 'APPROVAL_PENDING' && approval('execute_plan') && !approval('run_canary_rejudge')" class="ghost-button" @click="rejectAction('RUN_CANARY_REJUDGE','technical_approver','拒绝控制组与灰度重评')">拒绝控制与灰度</button>
          <button v-if="incident.canary_rejudge_passed && !approval('run_bulk_rejudge')" class="primary-button" @click="approveAction('RUN_BULK_REJUDGE','business_approver','批准影响集合内的全量重评')">业务审批：全量重评</button>
          <button v-if="incident.canary_rejudge_passed && !approval('run_bulk_rejudge')" class="ghost-button" @click="rejectAction('RUN_BULK_REJUDGE','business_approver','拒绝全量重评')">拒绝全量重评</button>
          <button v-if="verification && incident.stage === 'VERIFYING' && !approval('close_incident')" class="primary-button" @click="approveAction('CLOSE_INCIDENT','business_approver','确认验证结果并批准关闭事故')">业务审批：关闭事故</button>
          <button v-if="verification && incident.stage === 'VERIFYING' && !approval('close_incident')" class="ghost-button" @click="rejectAction('CLOSE_INCIDENT','business_approver','拒绝关闭事故')">拒绝关闭</button>
        </div>
        <p>只有人工审批由当前用户完成；实验、影响计算、重评和验证均由 AgentTeams 调度专业 Worker 通过受控工具执行。</p>
      </div>

      <article class="panel workspace-panel">
        <el-tabs v-model="tab">
          <el-tab-pane label="Agent 协同" name="agents">
            <div class="section-intro"><div><h3>协作事件与动态路由</h3><p>任务拆解、Worker 调用、工具结果、状态变化和人工门禁都会按顺序持久化。</p></div><span>{{ agentEvents.length }} 条</span></div>
            <div v-if="legalOptions.length" class="route-grid">
              <article v-for="option in legalOptions" :key="`${option.action}-${option.experiment_kind || ''}`" class="sub-card">
                <small>合法下一步</small><h3>{{ option.action }}</h3><p>{{ option.worker }} · {{ option.tool || '人工门禁' }}</p><em>{{ option.expected_result }}</em>
              </article>
            </div>
            <div v-if="agentEvents.length" class="agent-event-list">
              <article v-for="event in [...agentEvents].reverse()" :key="event.id">
                <i>{{ event.sequence }}</i><div><div><b>{{ event.event_type }}</b><span>{{ event.worker || event.agent }}</span><time>{{ new Date(event.created_at).toLocaleTimeString() }}</time></div><p>{{ event.summary }}</p><small v-if="event.tool">{{ event.action }} · {{ event.tool }}</small></div>
              </article>
            </div>
            <EmptyState v-else title="等待 AgentTeams 启动" description="启动后，Incident Manager 的路由决策和 Worker 工具结果会显示在这里。" />
          </el-tab-pane>
          <el-tab-pane label="信号与时间线" name="overview">
            <div class="section-intro"><div><h3>已归一化信号</h3><p>保留来源、时间和异常维度；时间相关性不会直接当作根因。</p></div><span>{{ workspace.signals.length }} 条</span></div>
            <div class="timeline-list"><div v-for="signal in workspace.signals" :key="signal.id"><time>{{ new Date(signal.observed_at).toLocaleString() }}</time><i></i><div><b>{{ signal.kind }} · {{ signal.source }}</b><p>{{ signal.summary }}</p><small>{{ signal.id }}</small></div></div></div>
          </el-tab-pane>

          <el-tab-pane label="根因与实验" name="diagnosis">
            <div class="hypothesis-grid"><article v-for="item in workspace.hypotheses" :key="item.id" class="sub-card" :class="{ confirmed: item.state === 'CONFIRMED' }"><div><StagePill :stage="item.state" /><span>{{ (item.confidence * 100).toFixed(0) }}% 置信度</span></div><h3>{{ item.category }}</h3><p>{{ item.statement }}</p><small>{{ item.id }}</small></article></div>
            <article v-if="experiment" class="experiment-card"><div class="panel-title"><h3>{{ experiment.title }}</h3><StagePill :stage="experiment.state" /></div><p>{{ experiment.conclusion }}</p><div class="metric-pairs"><span v-for="(value, key) in experiment.metrics" :key="key"><small>{{ key }}</small><b>{{ value }}</b></span></div></article>
          </el-tab-pane>

          <el-tab-pane label="影响范围" name="impact">
            <template v-if="impact"><div class="impact-grid"><div><small>受影响选手</small><strong>{{ impact.affected_candidate_count }}</strong></div><div><small>受影响提交</small><strong>{{ impact.affected_submission_count }}</strong></div><div><small>成绩变化</small><strong>{{ impact.projected_score_change_count }}</strong></div><div><small>晋级变化</small><strong>{{ impact.projected_advancement_change_count }}</strong></div></div><div class="scope-row"><span>题目：{{ impact.problem_ids.join('、') }}</span><span>语言：{{ impact.languages.join('、') }}</span><span>策略：{{ impact.policy }}</span></div><details><summary>查看受影响提交标识（{{ impact.submission_ids.length }}）</summary><pre class="code-block">{{ impact.submission_ids.join('\n') }}</pre></details></template><EmptyState v-else title="尚未计算影响范围" />
          </el-tab-pane>

          <el-tab-pane label="处置与审批" name="plan">
            <div v-if="plan" class="plan-list"><article v-for="(step, index) in plan.steps" :key="step.id" class="sub-card plan-step"><b>{{ index + 1 }}</b><div><div class="plan-head"><h3>{{ step.action }}</h3><span>{{ step.risk_level }}</span></div><dl><dt>前置条件</dt><dd>{{ step.preconditions.join('；') }}</dd><dt>成功检查</dt><dd>{{ step.success_checks.join('；') }}</dd><dt>停止条件</dt><dd>{{ step.stop_conditions.join('；') }}</dd><dt>回滚动作</dt><dd>{{ step.rollback_action }}</dd></dl></div></article></div>
            <div class="approval-table"><div v-for="item in workspace.approvals" :key="item.id"><span>{{ item.level }}</span><b>{{ item.action }}</b><small>{{ item.role_context }} · {{ item.actor }}</small><StagePill :stage="item.decision" /></div></div>
          </el-tab-pane>

          <el-tab-pane label="重评与成绩" name="rejudge">
            <div class="batch-grid"><article v-for="batch in workspace.rejudge_batches" :key="batch.id" class="sub-card"><div class="panel-title"><h3>#{{ batch.sequence }} {{ batch.kind }}</h3><StagePill :stage="batch.state" /></div><strong>{{ batch.completed_count }}/{{ batch.planned_count }}</strong><p>失败 {{ batch.failed_count }} · 跳过 {{ batch.skipped_count }}</p><small>{{ batch.idempotency_key }}</small></article></div>
            <div v-if="workspace.score_changes.length" class="table-wrap"><table><thead><tr><th>选手</th><th>原成绩</th><th>新成绩</th><th>原排名</th><th>新排名</th><th>晋级变化</th></tr></thead><tbody><tr v-for="item in workspace.score_changes.slice(0,20)" :key="item.id"><td>{{ item.candidate_id }}</td><td>{{ item.before_score }}</td><td>{{ item.after_score }}</td><td>{{ item.before_rank }}</td><td>{{ item.after_rank }}</td><td>{{ item.advancement_changed ? '是' : '否' }}</td></tr></tbody></table></div>
          </el-tab-pane>

          <el-tab-pane label="闭环验证" name="verification">
            <template v-if="verification"><div class="verification-head"><div><span>验证结论</span><h3>{{ verification.status }}</h3><p>{{ verification.summary }}</p></div><strong>{{ (verification.coverage_rate * 100).toFixed(0) }}<small>% 覆盖</small></strong></div><div class="check-grid"><div v-for="(passed, name) in verification.checks" :key="name" :class="{ passed }"><i>{{ passed ? '✓' : '!' }}</i><span>{{ name }}</span></div></div><div class="verification-facts"><span>重复重评 {{ verification.duplicate_rejudge_count }}</span><span>遗漏重评 {{ verification.missing_rejudge_count }}</span><span>越界回归 {{ verification.cross_scope_regression_count }}</span></div></template><EmptyState v-else title="等待闭环验证" description="所有批准批次完成后，可独立核验覆盖、重复、越界和成绩一致性。" />
          </el-tab-pane>
        </el-tabs>
      </article>
    </template>
    <EmptyState v-else-if="!store.loading" title="事故不存在或无法加载" :description="store.error" />
  </section>
</template>

<style scoped>
.agent-command-bar{display:grid;grid-template-columns:1fr minmax(260px,auto) auto;align-items:center;gap:20px;margin-bottom:18px;border-left:4px solid var(--accent)}.agent-command-bar h3{margin:6px 0}.agent-command-bar p{margin:0;color:var(--muted);font-size:12px}.runtime-state{display:flex;flex-direction:column;gap:4px;padding:10px 12px;border-radius:9px;background:#fff4eb;color:#9b4b17}.runtime-state.ready{background:#e9f8f2;color:#187453}.runtime-state small{max-width:320px}.route-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px}.route-grid h3{margin:6px 0}.route-grid p,.route-grid em{font-size:12px;color:var(--muted)}.agent-event-list{display:grid;gap:10px}.agent-event-list article{display:grid;grid-template-columns:32px 1fr;gap:12px;padding:13px;border:1px solid var(--line-soft);border-radius:10px}.agent-event-list article>i{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#fff0e7;color:var(--accent);font-style:normal;font-weight:800}.agent-event-list article>div>div{display:flex;gap:10px;align-items:center}.agent-event-list time{margin-left:auto;color:var(--muted);font-size:11px}.agent-event-list p{margin:6px 0;color:var(--text)}.agent-event-list small{color:var(--muted)}
.detail-head{display:flex;justify-content:space-between;gap:28px;align-items:flex-end;margin-bottom:22px}.detail-head h2{font-size:34px;margin:8px 0}.detail-head p{margin:0;color:var(--muted)}.back-link{display:block;margin-bottom:15px;color:var(--accent);font-size:12px}.head-actions{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.stage-track{display:grid;grid-template-columns:repeat(10,1fr);margin-bottom:18px;background:white;border:1px solid var(--line);border-radius:12px;overflow:hidden}.stage-track>div{position:relative;padding:12px 4px;text-align:center;color:#8d99a8;font-size:10px;border-right:1px solid var(--line-soft)}.stage-track>div:last-child{border:0}.stage-track i{display:grid;place-items:center;width:21px;height:21px;margin:0 auto 5px;border:1px solid #cfd7e2;border-radius:50%;font-style:normal}.stage-track .done{color:#1e6f57;background:#f2faf7}.stage-track .active{color:var(--accent);background:#fff7eb;font-weight:800}.stage-track .active i{border-color:var(--accent);background:var(--accent);color:white}.detail-metrics .status-word{font-size:21px}.action-strip{display:grid;grid-template-columns:minmax(190px,.7fr) minmax(180px,.5fr) minmax(360px,1.8fr);gap:18px;align-items:center;margin-bottom:18px;padding:17px 20px;background:#14263d;color:white;border-radius:12px}.action-strip small,.action-strip strong{display:block}.action-strip small{color:#94a8bd;margin-bottom:4px}.action-strip>p{grid-column:1/-1;margin:0;color:#9eb0c3;font-size:11px}.operator label{display:block;color:#94a8bd;font-size:10px}.operator input{width:100%;margin-top:5px;padding:8px 9px;border:1px solid #3a4c62;border-radius:7px;background:#0c1c2e;color:white}.workspace-panel{padding-top:10px}.section-intro{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}.section-intro h3{margin:0}.section-intro p{margin:6px 0;color:var(--muted)}.section-intro>span{font-weight:800;color:var(--accent)}.timeline-list>div{display:grid;grid-template-columns:170px 12px 1fr;gap:14px}.timeline-list time{font:10px var(--mono);color:var(--muted);padding-top:3px}.timeline-list i{position:relative;width:8px;height:8px;margin-top:4px;border-radius:50%;background:var(--accent)}.timeline-list i:after{content:'';position:absolute;left:3px;top:10px;width:1px;height:calc(100% + 47px);background:var(--line)}.timeline-list>div:last-child i:after{display:none}.timeline-list>div>div{padding-bottom:22px}.timeline-list b{font-size:12px}.timeline-list p{margin:6px 0;color:var(--muted)}.timeline-list small{font:10px var(--mono);color:#95a1af}.hypothesis-grid,.batch-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.sub-card{padding:16px;border:1px solid var(--line);border-radius:10px;background:var(--panel-soft)}.sub-card.confirmed{border-color:#8fcbb9;background:#f1faf7}.sub-card>div:first-child{display:flex;justify-content:space-between;align-items:center}.sub-card h3{margin:14px 0 7px}.sub-card p{color:var(--muted);line-height:1.6}.sub-card small{font:10px var(--mono);color:var(--muted)}.experiment-card{margin-top:14px;padding:18px;border-left:4px solid var(--accent);background:#f8fafc}.experiment-card>p{color:var(--muted)}.metric-pairs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.metric-pairs span{padding:10px;background:white;border:1px solid var(--line-soft);border-radius:7px;overflow:hidden}.metric-pairs small,.metric-pairs b{display:block;overflow-wrap:anywhere}.metric-pairs small{color:var(--muted);font-size:9px}.impact-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.impact-grid>div{padding:18px;background:var(--panel-soft);border-radius:9px}.impact-grid small,.impact-grid strong{display:block}.impact-grid small{color:var(--muted)}.impact-grid strong{font-size:28px;margin-top:8px}.scope-row{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.scope-row span{padding:7px 9px;border:1px solid var(--line);border-radius:7px;font-size:11px}.plan-list{display:grid;gap:10px}.plan-step{display:grid;grid-template-columns:34px 1fr;gap:12px}.plan-step>b{display:grid;place-items:center;width:29px;height:29px;border-radius:8px;background:var(--accent);color:white}.plan-head{display:flex;justify-content:space-between}.plan-head h3{margin:4px 0}.plan-head span{color:var(--accent);font-weight:800}.plan-step dl{display:grid;grid-template-columns:80px 1fr;gap:7px;margin:12px 0 0;font-size:11px}.plan-step dt{color:var(--muted)}.plan-step dd{margin:0}.approval-table{display:grid;margin-top:16px;border:1px solid var(--line);border-radius:9px;overflow:hidden}.approval-table>div{display:grid;grid-template-columns:50px 1fr 1fr auto;gap:12px;align-items:center;padding:11px 13px;border-bottom:1px solid var(--line-soft)}.approval-table>div:last-child{border:0}.approval-table small{color:var(--muted)}.batch-grid{grid-template-columns:repeat(3,1fr)}.batch-grid strong{font-size:24px}.batch-grid p{font-size:11px;margin:6px 0}.table-wrap{overflow:auto;margin-top:16px}.table-wrap table{width:100%;border-collapse:collapse;font-size:11px}.table-wrap th,.table-wrap td{padding:9px 10px;border-bottom:1px solid var(--line-soft);text-align:left}.verification-head{display:flex;justify-content:space-between;padding:22px;background:#f1faf7;border:1px solid #b8ded2;border-radius:11px}.verification-head h3{font-size:23px;margin:5px 0}.verification-head p{color:var(--muted)}.verification-head>strong{font-size:50px;color:#177052}.verification-head>strong small{font-size:11px}.check-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:14px 0}.check-grid>div{display:flex;gap:8px;align-items:center;padding:12px;border:1px solid #efc6c6;background:#fff5f5;border-radius:8px;font-size:11px}.check-grid>div.passed{border-color:#b8ded2;background:#f1faf7}.check-grid i{font-style:normal;font-weight:900}.verification-facts{display:flex;gap:10px}.verification-facts span{padding:8px 10px;background:var(--panel-soft);border-radius:7px;font-size:11px}@media(max-width:1100px){.stage-track{overflow:auto;grid-template-columns:repeat(10,100px)}.action-strip{grid-template-columns:1fr}.action-strip>p{grid-column:1}.metric-pairs,.impact-grid,.check-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:760px){.detail-head{display:block}.head-actions{margin-top:16px}.hypothesis-grid,.batch-grid,.metric-pairs,.impact-grid,.check-grid{grid-template-columns:1fr}.timeline-list>div{grid-template-columns:1fr}.timeline-list i{display:none}.approval-table>div{grid-template-columns:1fr}.verification-head{display:block}}
</style>
