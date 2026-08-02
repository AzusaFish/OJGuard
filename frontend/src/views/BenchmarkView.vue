<script setup lang="ts">
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { init, use, type EChartsType } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { api } from '@/api'
import EmptyState from '@/components/EmptyState.vue'
import type { BenchmarkReport } from '@/types'

const report = ref<BenchmarkReport | null>(null)
const chartNode = ref<HTMLElement | null>(null)
use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

let chart: EChartsType | null = null

async function render() {
  const loaded = await api.get<BenchmarkReport>('/benchmark/report')
  report.value = loaded
  await nextTick()
  if (!chartNode.value) return
  chart = init(chartNode.value)
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 30, right: 18, top: 16, bottom: 54, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: loaded.cases.map((item) => item.package_id.replace('BENCH-', 'B')), axisLabel: { color: '#8197a4' }, axisLine: { lineStyle: { color: '#1b3342' } } },
    yAxis: { type: 'value', name: 'ms', nameTextStyle: { color: '#8197a4' }, axisLabel: { color: '#8197a4' }, splitLine: { lineStyle: { color: 'rgba(123,170,194,.1)' } } },
    series: [{ type: 'bar', data: loaded.cases.map((item) => ({ value: item.duration_ms, itemStyle: { color: item.clean_package ? '#69b7ff' : '#79f2c4', borderRadius: [5,5,0,0] } })) }],
  })
}
function resize(){ chart?.resize() }
onMounted(() => { render(); window.addEventListener('resize', resize) })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>

<template><section class="page"><div class="page-head"><div><h2>每个数字都能重新计算。</h2><p>十个原创小型题包覆盖四类缺陷与干净对照。当前报告只评估确定性基线，明确不冒充 AgentTeams 或 LLM 效果。</p></div><button class="ghost-button" @click="render">重新读取报告</button></div>
  <template v-if="report"><div class="metric-grid"><article class="panel metric"><small>Defect Precision</small><strong>{{ (report.metrics.precision*100).toFixed(0) }}%</strong><em>{{ report.metrics.true_positive }} TP / {{ report.metrics.false_positive }} FP</em></article><article class="panel metric"><small>Defect Recall</small><strong>{{ (report.metrics.recall*100).toFixed(0) }}%</strong><em>{{ report.defect_count }} 个标注缺陷</em></article><article class="panel metric"><small>Clean false block</small><strong>{{ (report.metrics.clean_package_false_block_rate*100).toFixed(0) }}%</strong><em>2 个干净对照</em></article><article class="panel metric"><small>LLM Calls</small><strong>{{ report.metrics.llm_calls }}</strong><em>本报告无模型费用</em></article></div>
    <div class="two-column"><article class="panel"><div class="panel-title"><h3>单题包规则审计耗时</h3><span>LOWER IS BETTER</span></div><div ref="chartNode" class="chart"></div></article><aside class="panel"><div class="panel-title"><h3>报告边界</h3><span>{{ report.scope }}</span></div><p class="scope">这些用例用于验证规则引擎的回归稳定性。最终比赛报告还需补充 Agent 协作、真实执行证据完整率、重放率与成本数据。</p><div class="scope-stat"><span>题包</span><b>{{ report.case_count }}</b></div><div class="scope-stat"><span>平均耗时</span><b>{{ report.metrics.mean_duration_ms }} ms</b></div><div class="scope-stat"><span>P95</span><b>{{ report.metrics.p95_duration_ms }} ms</b></div></aside></div>
    <article class="panel cases"><div class="panel-title"><h3>逐题包结果</h3><span>EXPECTED ↔ OBSERVED</span></div><div class="data-list"><div v-for="item in report.cases" :key="item.package_id" class="data-row"><div><strong>{{ item.package_id }}</strong><small>{{ item.clean_package ? 'clean control' : item.expected.join(', ') }}</small></div><small>{{ item.observed.length ? item.observed.join(', ') : 'no finding' }}</small><span :class="item.matched?'accent':'danger-text'">{{ item.matched ? 'MATCH' : 'MISMATCH' }}</span></div></div></article>
  </template><EmptyState v-else title="基准报告未生成" description="运行 python -m scripts.run_benchmark。" /></section></template>

<style scoped>.chart{height:330px}.scope{color:var(--muted);font-size:12px;line-height:1.7}.scope-stat{display:flex;justify-content:space-between;padding:13px 0;border-bottom:1px solid var(--line-soft);font-size:12px}.scope-stat b{font:11px 'DM Mono';color:var(--mint)}.cases{margin-top:18px}</style>
