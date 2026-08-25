<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <span class="title">模型量化</span>
        <el-button type="primary" @click="openCreate">新建量化任务</el-button>
      </div>

      <el-table :data="jobs" v-loading="loading" row-key="id">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="源版本" width="100">
          <template #default="{ row }">{{ row.model_version_id }}</template>
        </el-table-column>
        <el-table-column prop="target_quant" label="目标档位" width="110">
          <template #default="{ row }">
            <el-tag size="small" type="warning">{{ row.target_quant }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="server_id" label="节点" width="80" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="140">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :status="row.status === 'failed' ? 'exception' : row.status === 'done' ? 'success' : ''" />
          </template>
        </el-table-column>
        <el-table-column prop="target_path" label="产物路径" min-width="260" show-overflow-tooltip />
        <el-table-column prop="error" label="错误" min-width="160" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="新建量化任务" width="560px">
      <el-form :model="createForm" label-width="110px">
        <el-form-item label="源模型版本" required>
          <el-select v-model="createForm.model_version_id" placeholder="选择 GGUF 版本" class="w-full">
            <el-option v-for="v in ggufVersions" :key="v.id" :label="v.label" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标量化档位" required>
          <el-select v-model="createForm.target_quant" class="w-full">
            <el-option v-for="q in quantTypes" :key="q" :label="q" :value="q" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行节点" required>
          <el-select v-model="createForm.server_id" placeholder="选择服务器" class="w-full">
            <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.status})`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon title="使用 llama-quantize 在本机将源 GGUF 量化为目标档位，完成后自动注册为新版本。" />
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { modelsApi, quantizeApi, serversApi } from '../api'

const jobs = ref([])
const servers = ref([])
const models = ref([])
const loading = ref(false)
const saving = ref(false)
const createVisible = ref(false)
let timer = null

const quantTypes = ['F16', 'Q8_0', 'Q6_K', 'Q5_K_M', 'Q5_K_S', 'Q4_K_M', 'Q4_K_S', 'Q3_K_L', 'Q3_K_M', 'Q3_K_S', 'Q2_K']

const createForm = reactive({ model_version_id: null, target_quant: 'Q4_K_M', server_id: null })

const ggufVersions = computed(() => {
  const list = []
  for (const m of models.value) {
    for (const v of m.versions || []) {
      if (v.format === 'gguf') {
        list.push({ id: v.id, label: `${m.name} / ${v.version} (${v.quantization})` })
      }
    }
  }
  return list
})

function statusType(status) {
  if (status === 'done') return 'success'
  if (status === 'running') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const resp = await quantizeApi.list()
    jobs.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(createForm, { model_version_id: null, target_quant: 'Q4_K_M', server_id: null })
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.model_version_id) return ElMessage.warning('请选择源模型版本')
  if (!createForm.server_id) return ElMessage.warning('请选择执行节点')
  saving.value = true
  try {
    await quantizeApi.create({ ...createForm })
    ElMessage.success('量化任务已创建')
    createVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await load()
  try {
    const [m, s] = await Promise.all([modelsApi.list(), serversApi.list()])
    models.value = m.data
    servers.value = s.data
  } catch (e) {
    ElMessage.error(e.message)
  }
  timer = setInterval(load, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
.w-full {
  width: 100%;
}
</style>
