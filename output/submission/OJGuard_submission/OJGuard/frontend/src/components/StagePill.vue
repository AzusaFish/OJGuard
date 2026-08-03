<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ stage: string }>()
const tone = computed(() => {
  if (['FAILED', 'ROLLED_BACK'].includes(props.stage)) return 'danger'
  if (['RESOLVED', 'COMPLETED', 'PASSED', 'APPROVED'].includes(props.stage)) return 'success'
  if (['HUMAN_REVIEW_REQUIRED', 'APPROVAL_PENDING', 'PAUSED', 'PENDING'].includes(props.stage)) return 'warning'
  return 'info'
})
const labels: Record<string, string> = {
  DETECTED: '已发现',
  TRIAGING: '信号研判',
  INVESTIGATING: '根因分析',
  IMPACT_ASSESSING: '影响评估',
  REMEDIATION_PLANNING: '处置规划',
  APPROVAL_PENDING: '等待审批',
  EXECUTING: '处置执行',
  REJUDGING: '可信重评',
  VERIFYING: '闭环验证',
  RESOLVED: '已解决',
  HUMAN_REVIEW_REQUIRED: '需要人工复核',
  PAUSED: '已暂停',
  ROLLED_BACK: '已回滚',
  FAILED: '审计失败',
  PLANNED: '已计划',
  RUNNING: '执行中',
  COMPLETED: '已完成',
  PASSED: '已通过',
  CONFIRMED: '已确认',
  REJECTED: '已拒绝',
  APPROVED: '已批准',
  PENDING: '待决定',
}
const label = computed(() => labels[props.stage] || props.stage.replaceAll('_', ' '))
</script>

<template><span class="stage-pill" :class="tone"><i></i>{{ label }}</span></template>
