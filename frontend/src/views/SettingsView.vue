<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '@/api'

const info = ref<Record<string, any> | null>(null)
const error = ref('')
onMounted(async () => { try { info.value = await api.get('/system') } catch (cause) { error.value = cause instanceof Error ? cause.message : '无法连接后端' } })
</script>

<template><section class="page"><div class="page-head"><div><h2>默认省钱，也默认安全。</h2><p>这里仅展示非敏感运行配置。API Key 永远不会通过健康检查、Trace、错误消息或前端返回。</p></div></div>
  <div v-if="info" class="settings-grid"><article class="panel"><div class="panel-title"><h3>大模型</h3><span :class="info.llm_calls_enabled?'warning-text':'accent'">{{ info.llm_calls_enabled?'REAL CALLS':'MOCK / OFF' }}</span></div><dl><dt>供应商</dt><dd>{{ info.provider }}</dd><dt>模型</dt><dd>{{ info.model }}</dd><dt>预警线</dt><dd>¥{{ info.budget_warning_cny }}</dd><dt>停止线</dt><dd>¥{{ info.budget_stop_cny }}</dd></dl><p class="hint">只有显式打开 LLM_REAL_CALLS_ENABLED 才允许业务调用；确定性规则、Runner 与前端不消耗模型预算。</p></article>
    <article class="panel"><div class="panel-title"><h3>RAG 预留</h3><span class="warning-text">{{ info.rag.enabled?'ENABLED':'DISABLED' }}</span></div><dl><dt>端口</dt><dd>{{ info.rag.port }}</dd><dt>接口</dt><dd>/api/v1/rag</dd><dt>当前供应商</dt><dd>未配置</dd></dl><p class="hint">初赛默认不启用知识库。接口契约和独立端口已保留，后续可以接入向量库而不改前端路由。</p></article>
    <article class="panel"><div class="panel-title"><h3>MCP</h3><span class="accent">READY</span></div><dl><dt>地址</dt><dd>{{ info.mcp.host }}:{{ info.mcp.port }}</dd><dt>传输</dt><dd>Streamable HTTP</dd><dt>路径</dt><dd>{{ info.mcp.path }}</dd></dl><p class="hint">Agent 只能使用已注册工具，无法直接访问宿主命令或 Docker API。</p></article>
    <article class="panel"><div class="panel-title"><h3>AgentTeams</h3><span class="accent">PINNED</span></div><dl><dt>版本</dt><dd>{{ info.agentteams.version }}</dd><dt>Team</dt><dd>{{ info.agentteams.team }}</dd><dt>Element</dt><dd>127.0.0.1:18088</dd></dl><p class="hint">本地部署需要明确决定 Docker Socket 权限；未授权时保持停止，不影响 OJGuard 单机审计核心。</p></article></div><p v-else class="danger-text">{{ error }}</p>
  <article class="panel secret-policy"><div><span>SECRET POLICY</span><h3>前端永远拿不到 DeepSeek API Key</h3></div><ul><li>.env 已被 Git 忽略</li><li>Pydantic SecretStr 屏蔽输出</li><li>健康接口只返回模型名与开关</li><li>AgentTeams 使用网关消费者身份</li></ul></article>
</section></template>

<style scoped>.settings-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.settings-grid dl{display:grid;grid-template-columns:1fr auto;gap:0;margin:0}.settings-grid dt,.settings-grid dd{padding:11px 0;border-bottom:1px solid var(--line-soft);font-size:11px}.settings-grid dt{color:var(--muted)}.settings-grid dd{margin:0;font:10px 'DM Mono';color:#cfe0e5}.hint{color:var(--muted);font-size:10px;line-height:1.6;margin:16px 0 0}.secret-policy{margin-top:18px;display:flex;justify-content:space-between;gap:30px}.secret-policy span{font:9px 'DM Mono';color:var(--mint)}.secret-policy h3{margin:8px 0}.secret-policy ul{margin:0;color:var(--muted);font-size:11px;line-height:1.9}@media(max-width:800px){.settings-grid{grid-template-columns:1fr}.secret-policy{display:block}}</style>
