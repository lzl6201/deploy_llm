<template>
  <div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="本地仓库" name="local">
        <el-card shadow="never">
          <div class="toolbar">
            <span class="title">模型仓库</span>
            <div>
              <el-button @click="openManual">手动登记</el-button>
              <el-button @click="openPrequantized">预量化导入</el-button>
              <el-button type="primary" @click="openImport">导入 GGUF 模型</el-button>
            </div>
          </div>

          <el-table :data="models" v-loading="loading" row-key="id">
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="version-panel">
                  <div class="version-header">
                    <span>版本列表（量化档位与基础精度分离）</span>
                    <el-button size="small" type="primary" plain @click="openAddVersion(row)">新增版本</el-button>
                  </div>
                  <el-table :data="row.versions" size="small">
                    <el-table-column prop="version" label="版本" width="140" />
                    <el-table-column prop="quantization" label="量化档位" width="110">
                      <template #default="{ row: v }">
                        <el-tag v-if="v.quantization !== 'none'" size="small" type="warning">{{ v.quantization }}</el-tag>
                        <el-tag v-else size="small" type="info">none</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="dtype" label="基础精度" width="100" />
                    <el-table-column prop="format" label="格式" width="110" />
                    <el-table-column label="大小" width="100">
                      <template #default="{ row: v }">
                        {{ v.size_gb != null ? v.size_gb + ' GB' : '-' }}
                      </template>
                    </el-table-column>
                    <el-table-column prop="storage_path" label="存储路径" min-width="280" show-overflow-tooltip />
                  </el-table>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="模型名" min-width="200" />
            <el-table-column prop="params_b" label="参数量(B)" width="100" />
            <el-table-column prop="architecture" label="架构" width="100" />
            <el-table-column prop="format" label="格式" width="110">
              <template #default="{ row }">
                <el-tag v-if="row.format === 'gguf'" size="small">GGUF</el-tag>
                <el-tag v-else-if="row.format === 'ollama'" size="small" type="success">Ollama</el-tag>
                <el-tag v-else size="small" type="info">Safetensors</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="dtype" label="基础精度" width="100" />
            <el-table-column prop="context_len" label="上下文" width="110" />
            <el-table-column label="版本数" width="80">
              <template #default="{ row }">{{ row.versions.length }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="HuggingFace" name="hf">
        <el-card shadow="never">
          <div class="toolbar">
            <span class="title">HuggingFace 模型</span>
            <div class="hf-search">
              <el-input v-model="hfQuery" placeholder="搜索模型，如 qwen / llama" clearable class="hf-search-input" @keyup.enter="hfSearch" />
              <el-button type="primary" :loading="hfLoading" @click="hfSearch">搜索</el-button>
              <el-button @click="openDownloads">下载任务</el-button>
            </div>
          </div>

          <div class="hf-orgs">
            <span class="hf-orgs-label">GGUF 组织：</span>
            <el-tag v-for="o in hfOrgs" :key="o" class="org-tag" effect="plain" @click="hfLoadOrg(o)">{{ o }}</el-tag>
          </div>

          <el-table :data="hfModels" v-loading="hfLoading" size="small" @row-click="openFiles">
            <el-table-column prop="id" label="模型" min-width="280" show-overflow-tooltip />
            <el-table-column label="下载量" width="110">
              <template #default="{ row }">{{ fmtCount(row.downloads) }}</template>
            </el-table-column>
            <el-table-column label="点赞" width="90">
              <template #default="{ row }">{{ fmtCount(row.likes) }}</template>
            </el-table-column>
            <el-table-column label="任务" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.pipeline_tag" size="small" type="info">{{ row.pipeline_tag }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click.stop="openFiles(row)">查看文件</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!hfLoading && hfModels.length === 0" description="搜索 HF 模型或点击上方 GGUF 组织" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 导入 GGUF 模型 -->
    <el-dialog v-model="importVisible" title="导入 GGUF 模型" width="640px">
      <el-form :model="importForm" label-width="110px">
        <el-form-item label="模型文件" required>
          <div class="path-picker">
            <el-input :model-value="importForm.path" readonly placeholder="请选择 .gguf 文件" />
            <el-button @click="fsVisible = true">选择</el-button>
          </div>
        </el-form-item>
        <el-form-item label="元数据">
          <el-descriptions v-if="inspectResult" :column="2" size="small" border>
            <el-descriptions-item label="名称">{{ inspectResult.name }}</el-descriptions-item>
            <el-descriptions-item label="参数量">{{ inspectResult.params_b }}B</el-descriptions-item>
            <el-descriptions-item label="量化档位">{{ inspectResult.file_type_label }}</el-descriptions-item>
            <el-descriptions-item label="架构">{{ inspectResult.architecture }}</el-descriptions-item>
            <el-descriptions-item label="上下文">{{ inspectResult.context_len }}</el-descriptions-item>
            <el-descriptions-item label="大小">{{ inspectResult.file_size_gb }} GB</el-descriptions-item>
          </el-descriptions>
          <div v-else class="hint">选择文件后自动解析元数据。</div>
        </el-form-item>
        <el-form-item label="版本号">
          <el-input v-model="importForm.version" placeholder="v1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!inspectResult" @click="submitImport">导入</el-button>
      </template>
    </el-dialog>

    <!-- 手动登记（Safetensors / Ollama 等非 GGUF） -->
    <el-dialog v-model="manualVisible" title="手动登记模型" width="560px">
      <el-form :model="manualForm" label-width="110px">
        <el-form-item label="模型名" required>
          <el-input v-model="manualForm.name" placeholder="如 Qwen2.5-7B-Instruct" />
        </el-form-item>
        <el-form-item label="参数量(B)" required>
          <el-input-number v-model="manualForm.params_b" :min="0" :step="1" />
        </el-form-item>
        <el-form-item label="架构">
          <el-input v-model="manualForm.architecture" placeholder="qwen2 / llama / ..." />
        </el-form-item>
        <el-form-item label="格式">
          <el-select v-model="manualForm.format">
            <el-option label="Safetensors (vLLM)" value="safetensors" />
            <el-option label="Ollama" value="ollama" />
            <el-option label="GGUF" value="gguf" />
          </el-select>
        </el-form-item>
        <el-form-item label="基础精度">
          <el-select v-model="manualForm.dtype">
            <el-option label="BF16" value="bf16" />
            <el-option label="FP16" value="fp16" />
            <el-option label="FP32" value="fp32" />
            <el-option label="FP8" value="fp8" />
          </el-select>
        </el-form-item>
        <el-form-item label="上下文长度">
          <el-input-number v-model="manualForm.context_len" :min="0" :step="1024" />
        </el-form-item>
        <el-form-item label="存储路径" required>
          <div class="path-picker">
            <el-input :model-value="manualForm.base_storage_path" readonly placeholder="选择目录或权重文件" />
            <el-button @click="fsVisible = true; fsAllowDir = true">选择</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitManual">确定</el-button>
      </template>
    </el-dialog>

    <!-- 预量化导入（FP8 / AWQ / GPTQ 等非 GGUF） -->
    <el-dialog v-model="prequantizedVisible" title="预量化导入" width="560px">
      <el-form :model="prequantizedForm" label-width="110px">
        <el-form-item label="模型名" required>
          <el-input v-model="prequantizedForm.name" placeholder="如 Qwen2.5-7B-Instruct" />
        </el-form-item>
        <el-form-item label="参数量(B)" required>
          <el-input-number v-model="prequantizedForm.params_b" :min="0" :step="1" />
        </el-form-item>
        <el-form-item label="量化档位" required>
          <el-select v-model="prequantizedForm.quantization">
            <el-option label="FP8" value="fp8" />
            <el-option label="AWQ-INT4" value="awq-int4" />
            <el-option label="GPTQ" value="gptq" />
          </el-select>
        </el-form-item>
        <el-form-item label="基础精度">
          <el-select v-model="prequantizedForm.dtype">
            <el-option label="BF16" value="bf16" />
            <el-option label="FP16" value="fp16" />
            <el-option label="FP32" value="fp32" />
          </el-select>
        </el-form-item>
        <el-form-item label="版本号">
          <el-input v-model="prequantizedForm.version" placeholder="如 v1 / fp8" />
        </el-form-item>
        <el-form-item label="架构">
          <el-input v-model="prequantizedForm.architecture" placeholder="qwen2 / llama / ..." />
        </el-form-item>
        <el-form-item label="上下文长度">
          <el-input-number v-model="prequantizedForm.context_len" :min="0" :step="1024" />
        </el-form-item>
        <el-form-item label="存储路径" required>
          <div class="path-picker">
            <el-input :model-value="prequantizedForm.storage_path" readonly placeholder="选择模型目录" />
            <el-button @click="fsVisible = true; fsAllowDir = true">选择</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="prequantizedVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitPrequantized">确定</el-button>
      </template>
    </el-dialog>

    <!-- 新增版本 -->
    <el-dialog v-model="versionVisible" title="新增版本" width="560px">
      <el-form :model="versionForm" label-width="110px">
        <el-form-item label="版本" required>
          <el-input v-model="versionForm.version" placeholder="如 v1" />
        </el-form-item>
        <el-form-item label="量化档位">
          <el-select v-model="versionForm.quantization">
            <el-option label="无 (none)" value="none" />
            <el-option label="FP8" value="fp8" />
            <el-option label="AWQ-INT4" value="awq-int4" />
            <el-option label="GPTQ" value="gptq" />
          </el-select>
        </el-form-item>
        <el-form-item label="基础精度">
          <el-select v-model="versionForm.dtype">
            <el-option label="BF16" value="bf16" />
            <el-option label="FP16" value="fp16" />
            <el-option label="FP32" value="fp32" />
          </el-select>
        </el-form-item>
        <el-form-item label="存储路径" required>
          <el-input v-model="versionForm.storage_path" placeholder="/mnt/models/..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="versionVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitVersion">确定</el-button>
      </template>
    </el-dialog>

    <!-- HF 仓库文件 -->
    <el-dialog v-model="filesVisible" :title="currentRepo" width="680px">
      <el-table :data="filesList" v-loading="filesLoading" size="small" max-height="420">
        <el-table-column prop="path" label="文件名" min-width="260" show-overflow-tooltip />
        <el-table-column label="大小" width="120">
          <template #default="{ row }">{{ fmtSize(row.size) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_gguf" size="small" type="warning">GGUF</el-tag>
            <el-tag v-else size="small" type="info">其他</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" type="primary" :disabled="!row.is_gguf" @click="downloadFile(row)">下载</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 下载任务 -->
    <el-dialog v-model="downloadsVisible" title="下载任务" width="720px">
      <el-table :data="downloads" size="small" max-height="420">
        <el-table-column label="模型文件" min-width="240">
          <template #default="{ row }">
            <div>{{ row.repo_id }}</div>
            <div class="hint">{{ row.filename }}</div>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="180">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.progress || 0)" :status="progressStatus(row.status)" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <FsBrowser v-model="fsVisible" :allow-dir="fsAllowDir" @select="onFsSelect" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fsApi, hfApi, modelsApi } from '../api'
import FsBrowser from '../components/FsBrowser.vue'

defineOptions({ name: 'Models' })

const activeTab = ref('local')

const models = ref([])
const loading = ref(false)
const saving = ref(false)

const importVisible = ref(false)
const importForm = reactive({ path: '', version: 'v1', source: 'local' })
const inspectResult = ref(null)

const manualVisible = ref(false)
const manualForm = reactive({ name: '', params_b: 7, architecture: '', dtype: 'bf16', format: 'safetensors', context_len: 32768, base_storage_path: '' })

const prequantizedVisible = ref(false)
const prequantizedForm = reactive({ name: '', params_b: 7, architecture: '', dtype: 'bf16', format: 'safetensors', quantization: 'fp8', version: 'v1', context_len: 32768, storage_path: '' })

const versionVisible = ref(false)
const versionForm = reactive({ version: '', quantization: 'none', dtype: 'bf16', storage_path: '' })
let currentModelId = null

const fsVisible = ref(false)
const fsAllowDir = ref(false)

// HuggingFace 状态
const hfQuery = ref('')
const hfLoading = ref(false)
const hfModels = ref([])
const hfOrgs = ref([])

const filesVisible = ref(false)
const filesLoading = ref(false)
const filesList = ref([])
const currentRepo = ref('')

const downloadsVisible = ref(false)
const downloads = ref([])
let downloadTimer = null
const refreshedForDone = new Set()

async function load() {
  loading.value = true
  try {
    const resp = await modelsApi.list()
    models.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function openImport() {
  Object.assign(importForm, { path: '', version: 'v1', source: 'local' })
  inspectResult.value = null
  fsAllowDir.value = false
  importVisible.value = true
}

function openManual() {
  Object.assign(manualForm, { name: '', params_b: 7, architecture: '', dtype: 'bf16', format: 'safetensors', context_len: 32768, base_storage_path: '' })
  manualVisible.value = true
}

function openPrequantized() {
  Object.assign(prequantizedForm, { name: '', params_b: 7, architecture: '', dtype: 'bf16', format: 'safetensors', quantization: 'fp8', version: 'v1', context_len: 32768, storage_path: '' })
  prequantizedVisible.value = true
}

async function submitPrequantized() {
  saving.value = true
  try {
    await modelsApi.prequantized({ ...prequantizedForm })
    ElMessage.success('预量化模型已导入')
    prequantizedVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function onFsSelect(path) {
  if (importVisible.value) {
    importForm.path = path
    await inspect(path)
  } else if (manualVisible.value) {
    manualForm.base_storage_path = path
  } else if (prequantizedVisible.value) {
    prequantizedForm.storage_path = path
  }
  fsAllowDir.value = false
}

async function inspect(path) {
  inspectResult.value = null
  try {
    const resp = await fsApi.inspect(path)
    inspectResult.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function submitImport() {
  saving.value = true
  try {
    await modelsApi.import({ ...importForm })
    ElMessage.success('模型已导入')
    importVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function submitManual() {
  saving.value = true
  try {
    await modelsApi.create({ ...manualForm })
    ElMessage.success('创建成功')
    manualVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

function openAddVersion(model) {
  currentModelId = model.id
  Object.assign(versionForm, { version: '', quantization: 'none', dtype: model.dtype, storage_path: model.base_storage_path })
  versionVisible.value = true
}

async function submitVersion() {
  saving.value = true
  try {
    await modelsApi.addVersion(currentModelId, { ...versionForm })
    ElMessage.success('版本已添加')
    versionVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

// ---- HuggingFace ----

async function loadOrgs() {
  try {
    const resp = await hfApi.orgs()
    hfOrgs.value = resp.data.orgs || []
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function hfSearch() {
  if (!hfQuery.value.trim()) return ElMessage.warning('请输入搜索关键词')
  hfLoading.value = true
  try {
    const resp = await hfApi.search({ query: hfQuery.value.trim(), limit: 30 })
    hfModels.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    hfLoading.value = false
  }
}

async function hfLoadOrg(org) {
  hfLoading.value = true
  try {
    const resp = await hfApi.orgModels(org, { limit: 30 })
    hfModels.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    hfLoading.value = false
  }
}

async function openFiles(repo) {
  currentRepo.value = repo.id
  filesVisible.value = true
  filesLoading.value = true
  filesList.value = []
  try {
    const resp = await hfApi.files(repo.id)
    filesList.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    filesLoading.value = false
  }
}

async function downloadFile(file) {
  try {
    await hfApi.download({ repo_id: currentRepo.value, filename: file.path, size_bytes: file.size })
    ElMessage.success('已创建下载任务')
    downloadsVisible.value = true
    startDownloadPolling()
    await loadDownloads()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function openDownloads() {
  downloadsVisible.value = true
  startDownloadPolling()
  loadDownloads()
}

async function loadDownloads() {
  try {
    const resp = await hfApi.downloads()
    downloads.value = resp.data
    const hasActive = downloads.value.some((d) => d.status === 'pending' || d.status === 'running')
    if (!hasActive && downloadTimer) stopDownloadPolling()
    // 每个新完成的下载（含注册出的 model_version_id）只刷新一次本地仓库
    downloads.value.forEach((d) => {
      if (d.status === 'done' && d.model_version_id && !refreshedForDone.has(d.id)) {
        refreshedForDone.add(d.id)
        load()
      }
    })
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function startDownloadPolling() {
  if (downloadTimer) return
  downloadTimer = setInterval(loadDownloads, 1500)
}

function stopDownloadPolling() {
  if (downloadTimer) {
    clearInterval(downloadTimer)
    downloadTimer = null
  }
}

function fmtCount(n) {
  if (n == null) return '-'
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'k'
  return String(n)
}

function fmtSize(bytes) {
  if (!bytes) return '-'
  if (bytes >= 1024 * 1024 * 1024) return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
  if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  return (bytes / 1024).toFixed(1) + ' KB'
}

function statusLabel(s) {
  return { pending: '等待中', running: '下载中', done: '完成', failed: '失败' }[s] || s
}

function statusType(s) {
  return { pending: 'info', running: 'primary', done: 'success', failed: 'danger' }[s] || 'info'
}

function progressStatus(s) {
  return s === 'done' ? 'success' : s === 'failed' ? 'exception' : ''
}

onMounted(() => {
  load()
  loadOrgs()
})

onBeforeUnmount(stopDownloadPolling)
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
.version-panel {
  padding: 8px 24px;
}
.version-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.path-picker {
  display: flex;
  gap: 8px;
  width: 100%;
}
.path-picker .el-input {
  flex: 1;
}
.hint {
  color: #909399;
  font-size: 13px;
}
.hf-search {
  display: flex;
  gap: 8px;
  align-items: center;
}
.hf-search-input {
  width: 280px;
}
.hf-orgs {
  margin-bottom: 12px;
  color: #606266;
  font-size: 13px;
}
.hf-orgs-label {
  margin-right: 4px;
}
.org-tag {
  margin-right: 8px;
  cursor: pointer;
}
</style>
