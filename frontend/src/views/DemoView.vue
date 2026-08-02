<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { api } from '@/api'
import type { RunContext } from '@/types'

const router = useRouter()
const running = ref(false)
const result = ref<any>(null)

async function runDemo() {
  running.value = true
  result.value = null
  try {
    result.value = await api.post('/workflow/demo/audit')
    ElMessage.success('四项探针均已完成，证据已固化')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : 'Demo 执行失败')
  } finally {
    running.value = false
  }
}

function openRun() {
  const context = result.value?.context as RunContext | undefined
  if (context) router.push(`/runs/${context.run_id}`)
}
</script>

<template>
  <section class="page">
    <div class="page-head"><div><h2>四个缺陷，一条证据链。</h2><p>原创 Maximum Segment Score 题包同时预埋规格冲突、32 位溢出、错解漏测和 Checker 尾随输出绕过。所有结论由 Docker Runner 真实执行。</p></div></div>
    <div class="two-column">
      <article class="panel demo-card">
        <span class="demo-index">DEMO / 001</span><h3>Maximum Segment Score</h3>
        <div class="defect-grid">
          <div><b>01</b><span>Validator 边界</span><small>题面允许，校验器拒绝</small></div>
          <div><b>02</b><span>整数溢出</span><small>Oracle 与参考解分歧</small></div>
          <div><b>03</b><span>负数漏测</span><small>新增反例淘汰错解</small></div>
          <div><b>04</b><span>Checker 绕过</span><small>非法尾随输出被接受</small></div>
        </div>
        <div class="button-row">
          <button class="primary-button" :disabled="running" @click="runDemo">{{ running ? 'Docker 沙箱执行中…' : '开始完整审计' }}</button>
          <button v-if="result" class="ghost-button" @click="openRun">查看运行详情</button>
        </div>
      </article>
      <aside class="panel">
        <div class="panel-title"><h3>执行路径</h3><span>NO LLM REQUIRED</span></div>
        <ol class="steps">
          <li><b>规则审计</b><span>生成 4 条可证伪假设</span></li><li><b>隔离执行</b><span>编译 Oracle、参考解与错解</span></li><li><b>对抗探针</b><span>运行 Validator 和 Checker 攻击</span></li><li><b>证据固化</b><span>JSON + SHA-256 + Trace</span></li><li><b>发布门禁</b><span>严重 Finding 自动阻断</span></li>
        </ol>
      </aside>
    </div>
    <article v-if="result" class="panel result-strip">
      <div><small>RUN ID</small><b>{{ result.context.run_id }}</b></div><div><small>DECISION</small><b class="danger-text">{{ result.release_gate.decision }}</b></div><div><small>FINDINGS</small><b>{{ result.findings.length }}</b></div><div><small>EVIDENCE</small><b>{{ result.evidence.length }}</b></div>
    </article>
  </section>
</template>

<style scoped>
.demo-card h3 { margin: 12px 0 22px; font-size: 28px; }.demo-index { color: var(--mint); font: 10px 'DM Mono'; }.defect-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 24px; }.defect-grid div { padding: 15px; border: 1px solid var(--line); border-radius: 12px; background: rgba(255,255,255,.018); }.defect-grid b { color: var(--red); font: 10px 'DM Mono'; }.defect-grid span, .defect-grid small { display: block; }.defect-grid span { margin-top: 9px; font-weight: 700; font-size: 13px; }.defect-grid small { color: var(--muted); margin-top: 4px; font-size: 10px; }.steps { margin: 0; padding: 0; list-style: none; counter-reset: step; }.steps li { position: relative; padding: 3px 0 20px 30px; border-left: 1px solid var(--line); }.steps li:last-child { border: 0; }.steps li::before { content: ''; position: absolute; left: -4px; top: 5px; width: 7px; height: 7px; border-radius: 50%; background: var(--mint); box-shadow: 0 0 10px rgba(121,242,196,.4); }.steps b, .steps span { display: block; }.steps b { font-size: 12px; }.steps span { margin-top: 3px; color: var(--muted); font-size: 10px; }.result-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 18px; }.result-strip small, .result-strip b { display: block; }.result-strip small { color: var(--muted); font: 9px 'DM Mono'; }.result-strip b { margin-top: 7px; font: 13px 'DM Mono'; overflow-wrap: anywhere; } @media(max-width:700px){.defect-grid,.result-strip{grid-template-columns:1fr 1fr}}
</style>
