<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ stage: string }>()
const tone = computed(() => {
  if (['BLOCKED', 'FAILED', 'BUDGET_EXHAUSTED'].includes(props.stage)) return 'danger'
  if (['READY_FOR_RELEASE', 'PASS_CANDIDATE', 'REGRESSION_PASSED', 'RELEASE_CONFIRMED'].includes(props.stage)) return 'success'
  if (['HUMAN_REVIEW_REQUIRED', 'PATCH_PENDING_APPROVAL', 'REVALIDATING'].includes(props.stage)) return 'warning'
  return 'info'
})
</script>

<template><span class="stage-pill" :class="tone"><i></i>{{ stage.replaceAll('_', ' ') }}</span></template>
