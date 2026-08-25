<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="16">
        <el-card shadow="never">
          <template #header><span class="title">一键部署</span></template>
          <el-form :model="form" label-width="110px">
            <el-form-item label="模型">
              <el-select v-model="form.model_id" placeholder="选择模型" @change="onModelChange" class="w-full">
                <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="版本">
              <el-select v-model="form.model_version_id" placeholder="选择版本" @change="onVersionChange" class="w-full">
                <el-option
                  v-for="v in versions"
                  :key="v.id"
                  :label="`${v.version} (${v.quantization})`"
                  :value="v.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="引擎">
              <el-select v-model="form.engine" class="w-full">
                <el-option v-for="e in engines" :key="e.name" :label="e.name" :value="e.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="服务器">
              <el-select v-model="form.server_id" placeholder="选择目标服务器" @change="onServerChange" class="w-full">
                <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.status})`" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="GPU 卡">
              <el-checkbox-group v-model="form.gpu_ids">
                <el-checkbox v-for="g in gpus" :key="g.index" :value="g.index" border>
                  GPU{{ g.index }} ({{ (g.vram_total_mb / 1024).toFixed(0) }}G)
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item label="张量并行 TP">
              <el-input-number v-model="form.tp_size" :min="1" :max="8" />
            </el-form-item>
            <el-form-item label="端口">
              <el-input-number v-model="form.port" :min="1024" :max="65535" />
            </el-form-item>
            <el-form-item label="最大上下文">
              <el-input-number v-model="form.max_model_len" :min="1024" :step="1024" />
            </el-form-item>
            <el-form-item label="部署名称">
              <el-input v-model="form.name" placeholder="留空自动生成" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="submit">部署</el-button>
              <el-button @click="doRecommend" :loading="recommending">智能推荐</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never">
          <template #header><span class="title">智能推荐结果</span></template>
          <div v-if="!recommendResult" class="hint">选择模型与服务器后，点击「智能推荐」获取最佳部署方案。</div>
          <el-descriptions v-else :column="1" border>
            <el-descriptions-item label="推荐引擎">{{ recommendResult.engine }}</el-descriptions-item>
            <el-descriptions-item label="并行度 TP">{{ recommendResult.tp_size }}</el-descriptions-item>
            <el-descriptions-item label="量化档位">{{ recommendResult.quantization }}</el-descriptions-item>
            <el-descriptions-item label="推荐上下文">{{ recommendResult.recommended_ctx_len }}</el-descriptions-item>
            <el-descriptions-item label="单卡可容纳">{{ recommendResult.fits_single_gpu ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="预估显存">{{ (recommendResult.estimated_vram_mb / 1024).toFixed(1) }} GB</el-descriptions-item>
            <el-descriptions-item label="说明">{{ recommendResult.note }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { deploymentsApi, enginesApi, modelsApi, recommendApi, serversApi } from '../api'

const router = useRouter()

const models = ref([])
const servers = ref([])
const engines = ref([])
const submitting = ref(false)
const recommending = ref(false)
const recommendResult = ref(null)

const form = reactive({
  model_id: null,
  model_version_id: null,
  engine: 'vllm',
  server_id: null,
  gpu_ids: [],
  tp_size: 1,
  port: 8001,
  max_model_len: 32768,
  name: '',
})

const versions = computed(() => {
  const model = models.value.find((m) => m.id === form.model_id)
  return model ? model.versions : []
})

const gpus = computed(() => {
  const server = servers.value.find((s) => s.id === form.server_id)
  return server ? server.gpus : []
})

const currentModel = computed(() => models.value.find((m) => m.id === form.model_id))
const currentVersion = computed(() => versions.value.find((v) => v.id === form.model_version_id))

function onModelChange() {
  form.model_version_id = null
  form.gpu_ids = []
  form.tp_size = 1
  if (versions.value.length > 0) {
    form.model_version_id = versions.value[0].id
    onVersionChange()
  }
}

function onVersionChange() {
  form.gpu_ids = []
  form.tp_size = 1
  // 依据模型格式自动选择引擎
  const v = currentVersion.value
  if (v) {
    if (v.format === 'gguf') form.engine = 'llama.cpp'
    else if (v.format === 'ollama') form.engine = 'ollama'
    else if (engines.value.some((e) => e.name === 'vllm')) form.engine = 'vllm'
  }
}

function onServerChange() {
  form.gpu_ids = []
}

async function doRecommend() {
  if (!form.model_version_id) {
    ElMessage.warning('请先选择模型版本')
    return
  }
  if (!form.server_id) {
    ElMessage.warning('请先选择服务器')
    return
  }
  recommending.value = true
  try {
    const resp = await recommendApi.plan({
      model_version_id: form.model_version_id,
      server_id: form.server_id,
    })
    recommendResult.value = resp.data
    form.tp_size = resp.data.tp_size
    if (resp.data.engine) form.engine = resp.data.engine
    if (resp.data.recommended_ctx_len) form.max_model_len = resp.data.recommended_ctx_len
    form.gpu_ids = gpus.value.slice(0, resp.data.tp_size).map((g) => g.index)
    ElMessage.success('推荐完成')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    recommending.value = false
  }
}

async function submit() {
  if (!form.model_version_id) return ElMessage.warning('请选择模型版本')
  if (!form.server_id) return ElMessage.warning('请选择服务器')
  submitting.value = true
  try {
    const payload = { ...form }
    if (!payload.name) {
      const mv = currentVersion.value
      payload.name = `${currentModel.value.name}-${mv?.version || 'v1'}-${payload.engine}`
    }
    await deploymentsApi.create(payload)
    ElMessage.success('部署任务已创建')
    router.push('/deployments')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const [m, s, e] = await Promise.all([modelsApi.list(), serversApi.list(), enginesApi.list()])
    models.value = m.data
    servers.value = s.data
    engines.value = e.data
    if (engines.value.length > 0) form.engine = engines.value[0].name
  } catch (err) {
    ElMessage.error(err.message)
  }
})
</script>

<style scoped>
.title {
  font-size: 16px;
  font-weight: 600;
}
.w-full {
  width: 100%;
}
.hint {
  color: #909399;
  font-size: 13px;
  padding: 12px 0;
}
</style>
