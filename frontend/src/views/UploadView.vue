<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { api } from '@/api'

const packageId = ref('')
const file = ref<File | null>(null)
const uploading = ref(false)
const manifest = ref<any>(null)

function choose(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] || null
}

async function upload() {
  if (!packageId.value || !file.value) return ElMessage.warning('请填写题包 ID 并选择 ZIP')
  const body = new FormData()
  body.append('package_id', packageId.value)
  body.append('archive', file.value)
  uploading.value = true
  try {
    manifest.value = await api.upload('/runs/packages', body)
    ElMessage.success('题包已安全解压，原始副本已锁定')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '上传失败')
  } finally { uploading.value = false }
}
</script>

<template>
  <section class="page"><div class="page-head"><div><h2>把题包作为不可信输入。</h2><p>仅接受 ZIP；接入阶段检查大小、数量、重复路径、目录穿越与符号链接。原始题包一经接入保持不可变。</p></div></div>
    <div class="two-column"><article class="panel upload-panel"><label>题包 ID</label><el-input v-model="packageId" placeholder="例如 contest-round-a" maxlength="100" />
      <label>题包 ZIP</label><label class="drop-zone"><input type="file" accept=".zip,application/zip" @change="choose" /><b>{{ file?.name || '选择或拖入 ZIP 文件' }}</b><small>{{ file ? `${(file.size/1024).toFixed(1)} KiB` : '最大 20 MiB · 不接受符号链接' }}</small></label>
      <button class="primary-button" :disabled="uploading" @click="upload">{{ uploading ? '正在检查…' : '接入并验证结构' }}</button>
    </article><aside class="panel"><div class="panel-title"><h3>接入策略</h3><span>L0 SAFE</span></div><ul class="policy"><li>压缩包 ≤ 20 MiB</li><li>解压后 ≤ 100 MiB</li><li>文件数 ≤ 2,000</li><li>拒绝绝对路径、.. 与链接</li><li>保存 source.zip 的 SHA-256</li><li>结构检查阶段不执行任何代码</li></ul></aside></div>
    <article v-if="manifest" class="panel manifest"><div class="panel-title"><h3>接入结果</h3><span>IMMUTABLE ORIGINAL</span></div><pre class="code-block">{{ JSON.stringify(manifest, null, 2) }}</pre></article>
  </section>
</template>

<style scoped>
.upload-panel { display: grid; gap: 12px; }.upload-panel label { color: var(--muted); font-size: 11px; margin-top: 6px; }.drop-zone { min-height: 170px; border: 1px dashed #315267; border-radius: 14px; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; background: rgba(121,242,196,.025); }.drop-zone input { display: none; }.drop-zone b { color: var(--text); font-size: 13px; }.drop-zone small { margin-top: 8px; font: 10px 'DM Mono'; }.policy { padding: 0; margin: 0; list-style: none; }.policy li { padding: 12px 0 12px 20px; border-bottom: 1px solid var(--line-soft); color: #b3c2c9; font-size: 12px; position: relative; }.policy li::before { content: '✓'; position: absolute; left: 0; color: var(--mint); }.manifest { margin-top: 18px; }
</style>
