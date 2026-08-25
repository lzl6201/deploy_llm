<template>
  <div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="智能推荐" name="plan">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-card shadow="never">
              <template #header><span class="title">部署条件</span></template>
              <el-form label-width="90px">
                <el-form-item label="模型">
                  <el-select v-model="modelId" placeholder="选择模型" class="w-full" @change="onModelChange">
                    <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
                  </el-select>
                </el-form-item>
                <el-form-item label="版本">
                  <el-select v-model="versionId" placeholder="选择版本" class="w-full">
                    <el-option
                      v-for="v in versions"
                      :key="v.id"
                      :label="`${v.version} · ${v.quantization}`"
                      :value="v.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="目标节点">
                  <el-select v-model="serverId" placeholder="选择服务器" class="w-full" @change="onServerChange">
                    <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.status})`" :value="s.id" />
                  </el-select>
                </el-form-item>
                <el-form-item label="可用显卡">
                  <div v-if="gpus.length === 0" class="hint">选择节点后显示其 GPU。</div>
                  <el-tag v-for="g in gpus" :key="g.index" class="gpu-tag" size="small">
                    GPU{{ g.index }} {{ (g.vram_total_mb / 1024).toFixed(0) }}G
                  </el-tag>
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="loading" @click="doPlan">智能推荐</el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>

          <el-col :span="16">
            <el-card shadow="never">
              <template #header><span class="title">推荐方案</span></template>
              <el-empty v-if="!result" description="选择模型、版本与节点后点击「智能推荐」" />

              <template v-else>
                <el-result
                  :icon="result.fits ? 'success' : 'error'"
                  :title="result.note"
                  :sub-title="`${result.engine} · TP=${result.tp_size} · 量化 ${result.quantization} · 上下文 ${result.recommended_ctx_len}`"
                >
                  <template #extra>
                    <el-tag size="large" :type="result.fits ? (result.fits_single_gpu ? 'success' : 'warning') : 'danger'">
                      {{ result.fits ? (result.fits_single_gpu ? '单卡可容纳' : `需 ${result.tp_size} 卡`) : '无法容纳' }}
                    </el-tag>
                  </template>
                </el-result>

                <el-row :gutter="12" class="metrics">
                  <el-col :span="6"><div class="metric"><span class="num">{{ gb(result.weight_mb) }}</span><span class="label">权重 (GB)</span></div></el-col>
                  <el-col :span="6"><div class="metric"><span class="num">{{ gb(result.kv_cache_mb) }}</span><span class="label">KV Cache (GB)</span></div></el-col>
                  <el-col :span="6"><div class="metric"><span class="num">{{ gb(result.estimated_vram_mb) }}</span><span class="label">预估总显存 (GB)</span></div></el-col>
                  <el-col :span="6"><div class="metric"><span class="num">{{ result.recommended_ctx_len }}</span><span class="label">推荐上下文</span></div></el-col>
                </el-row>

                <div class="vram-bar">
                  <div class="bar-track">
                    <div class="bar-weight" :style="{ width: weightPct }" />
                    <div class="bar-kv" :style="{ width: kvPct, left: weightPct }" />
                  </div>
                  <div class="bar-legend">
                    <span><i class="dot dot-weight" />权重</span>
                    <span><i class="dot dot-kv" />KV Cache</span>
                    <span class="bar-cap">容量 {{ gb(totalVram) }} GB</span>
                  </div>
                </div>

                <h4 class="sub-title">备选方案</h4>
                <el-table :data="result.alternatives" size="small" max-height="260">
                  <el-table-column prop="quantization" label="量化档位" width="120" />
                  <el-table-column prop="tp_size" label="TP" width="70" />
                  <el-table-column prop="ctx_len" label="上下文" width="110" />
                  <el-table-column label="总显存" width="120">
                    <template #default="{ row }">{{ gb(row.total_mb) }} GB</template>
                  </el-table-column>
                  <el-table-column label="是否可行" width="100">
                    <template #default="{ row }">
                      <el-tag :type="row.fits ? 'success' : 'info'" size="small">{{ row.fits ? '可容纳' : '超出' }}</el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </template>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="可部署模型" name="models">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span class="title">根据节点显卡，推荐可部署的模型</span>
              <div class="header-actions">
                <el-select v-model="reverseServerId" placeholder="选择节点" style="width: 260px" @change="loadDeployable">
                  <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.status})`" :value="s.id" />
                </el-select>
                <el-button type="primary" :loading="reverseLoading" :disabled="!reverseServerId" @click="loadDeployable">
                  分析
                </el-button>
              </div>
            </div>
          </template>

          <el-empty v-if="!reverseResults" description="选择节点后点击「分析」，列出仓库中每个模型版本的可部署性" />

          <template v-else>
            <div class="summary">
              共 {{ reverseResults.length }} 个模型版本，其中
              <el-tag type="success" size="small">{{ fittingCount }} 个可部署</el-tag>
              <el-tag type="danger" size="small">{{ reverseResults.length - fittingCount }} 个超出显存</el-tag>
            </div>
            <el-table :data="reverseResults" size="small" v-loading="reverseLoading" max-height="520">
              <el-table-column label="是否可部署" width="110" fixed>
                <template #default="{ row }">
                  <el-tag :type="row.fits ? 'success' : 'danger'" size="small">{{ row.fits ? '可部署' : '超出' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="model_name" label="模型" min-width="180" show-overflow-tooltip />
              <el-table-column prop="version" label="版本" width="90" />
              <el-table-column label="格式" width="110">
                <template #default="{ row }">{{ formatLabel(row.format) }}</template>
              </el-table-column>
              <el-table-column label="参数量" width="90">
                <template #default="{ row }">{{ row.params_b ? row.params_b.toFixed(1) + 'B' : '-' }}</template>
              </el-table-column>
              <el-table-column prop="quantization" label="量化" width="100" />
              <el-table-column prop="dtype" label="精度" width="80" />
              <el-table-column prop="engine" label="引擎" width="100" />
              <el-table-column label="TP" width="60">
                <template #default="{ row }">{{ row.tp_size }}</template>
              </el-table-column>
              <el-table-column label="推荐上下文" width="110">
                <template #default="{ row }">{{ row.recommended_ctx_len }}</template>
              </el-table-column>
              <el-table-column label="预估显存" width="110">
                <template #default="{ row }">{{ gb(row.estimated_vram_mb) }} GB</template>
              </el-table-column>
              <el-table-column prop="note" label="说明" min-width="200" show-overflow-tooltip />
            </el-table>
          </template>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

defineOptions({ name: 'Recommend' })
import { ElMessage } from 'element-plus'
import { modelsApi, recommendApi, serversApi } from '../api'

const activeTab = ref('plan')

const models = ref([])
const servers = ref([])
const modelId = ref(null)
const versionId = ref(null)
const serverId = ref(null)
const result = ref(null)
const loading = ref(false)

const reverseServerId = ref(null)
const reverseLoading = ref(false)
const reverseResults = ref(null)

const versions = computed(() => {
  const m = models.value.find((x) => x.id === modelId.value)
  return m ? m.versions : []
})
const server = computed(() => servers.value.find((s) => s.id === serverId.value))
const gpus = computed(() => (server.value ? server.value.gpus : []))
const totalVram = computed(() => gpus.value.reduce((s, g) => s + g.vram_total_mb, 0))
const fittingCount = computed(() => (reverseResults.value || []).filter((r) => r.fits).length)

const weightPct = computed(() => {
  if (!totalVram.value || !result.value) return '0%'
  return Math.min(100, (result.value.weight_mb / totalVram.value) * 100) + '%'
})
const kvPct = computed(() => {
  if (!totalVram.value || !result.value) return '0%'
  return Math.min(100, (result.value.kv_cache_mb / totalVram.value) * 100) + '%'
})

function onModelChange() {
  versionId.value = null
  if (versions.value.length > 0) versionId.value = versions.value[0].id
}

function onServerChange() {
  if (reverseServerId.value === null) reverseServerId.value = serverId.value
}

function gb(mb) {
  return mb ? (mb / 1024).toFixed(1) : '0.0'
}

function formatLabel(f) {
  return { gguf: 'GGUF', safetensors: 'Safetensors', ollama: 'Ollama' }[f] || f
}

async function doPlan() {
  if (!versionId.value) return ElMessage.warning('请选择模型版本')
  if (!serverId.value) return ElMessage.warning('请选择目标节点')
  loading.value = true
  try {
    const resp = await recommendApi.plan({ model_version_id: versionId.value, server_id: serverId.value })
    result.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function loadDeployable() {
  if (!reverseServerId.value) return ElMessage.warning('请选择节点')
  reverseLoading.value = true
  try {
    const resp = await recommendApi.models(reverseServerId.value)
    reverseResults.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    reverseLoading.value = false
  }
}

onMounted(async () => {
  try {
    const [m, s] = await Promise.all([modelsApi.list(), serversApi.list()])
    models.value = m.data
    servers.value = s.data
  } catch (e) {
    ElMessage.error(e.message)
  }
})
</script>

<style scoped>
.title {
  font-size: 16px;
  font-weight: 600;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.summary {
  margin-bottom: 12px;
  color: #606266;
  font-size: 13px;
}
.summary .el-tag {
  margin: 0 4px;
}
.w-full {
  width: 100%;
}
.hint {
  color: #909399;
  font-size: 13px;
}
.gpu-tag {
  margin-right: 6px;
  margin-bottom: 4px;
}
.metrics {
  margin: 12px 0 20px;
}
.metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 4px;
  background: #f5f7fa;
  border-radius: 6px;
}
.metric .num {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.metric .label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.vram-bar {
  margin-bottom: 20px;
}
.bar-track {
  position: relative;
  height: 18px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}
.bar-weight {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: #409eff;
}
.bar-kv {
  position: absolute;
  top: 0;
  height: 100%;
  background: #e6a23c;
}
.bar-legend {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
}
.bar-legend .bar-cap {
  margin-left: auto;
}
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 4px;
  vertical-align: middle;
}
.dot-weight {
  background: #409eff;
}
.dot-kv {
  background: #e6a23c;
}
.sub-title {
  font-size: 14px;
  font-weight: 600;
  margin: 16px 0 8px;
}
</style>
