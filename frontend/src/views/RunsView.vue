<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import EmptyState from '@/components/EmptyState.vue'
import StagePill from '@/components/StagePill.vue'
import { useRunsStore } from '@/stores/runs'

const store = useRunsStore()
const search = ref('')
const filtered = computed(() => store.runs.filter((item) => `${item.run_id} ${item.package_id} ${item.stage}`.toLowerCase().includes(search.value.toLowerCase())))
onMounted(store.loadRuns)
</script>

<template><section class="page"><div class="page-head"><div><h2>每次判断都有上下文。</h2><p>任务状态、假设、Finding、证据、审批与 Trace 使用同一个 run_id 串联。</p></div><el-input v-model="search" placeholder="搜索 ID / 状态" style="max-width:280px" clearable /></div>
  <article class="panel"><div v-if="filtered.length" class="data-list"><RouterLink v-for="run in filtered" :key="run.run_id" class="data-row run-row" :to="`/runs/${run.run_id}`"><div><strong>{{ run.package_id }}</strong><small>{{ run.run_id }}</small></div><div class="counts"><span>{{ run.confirmed_finding_ids.length }} findings</span><span>{{ run.evidence_ids.length }} evidence</span></div><StagePill :stage="run.stage" /></RouterLink></div><EmptyState v-else title="没有匹配的运行" description="运行主 Demo 后会在这里出现完整记录。" /></article>
</section></template>

<style scoped>.counts { display:flex; gap:12px; color:var(--muted); font:10px 'DM Mono'; }</style>
