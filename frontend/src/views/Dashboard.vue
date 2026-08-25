<template>
  <div>
    <div class="toolbar">
      <span class="page-desc">节点由 Agent 自动注册，也可在此手动登记未接入的服务器。</span>
      <div class="toolbar-actions">
        <el-button @click="load" :loading="loading">刷新</el-button>
        <el-button type="primary" @click="openAdd">登记节点</el-button>
      </div>
    </div>

    <div class="stat-row">
      <el-card shadow="never">
        <div class="stat"><span class="num">{{ servers.length }}</span><span class="label">服务器</span></div>
      </el-card>
      <el-card shadow="never">
        <div class="stat"><span class="num">{{ totalGpus }}</span><span class="label">GPU 总数</span></div>
      </el-card>
      <el-card shadow="never">
        <div class="stat"><span class="num">{{ onlineCount }}</span><span class="label">在线节点</span></div>
      </el-card>
      <el-card shadow="never">
        <div class="stat"><span class="num">{{ avgUtil.toFixed(1) }}%</span><span class="label">平均利用率</span></div>
      </el-card>
    </div>

    <el-row :gutter="16">
      <el-col v-for="srv in servers" :key="srv.id" :xs="24" :sm="12" :lg="8" class="srv-col">
        <el-card shadow="hover" class="srv-card">
          <template #header>
            <div class="srv-header">
              <span class="srv-name">{{ srv.hostname }}</span>
              <div class="srv-badges">
                <el-tag v-if="srv.source === 'manual'" size="small" type="info">手动登记</el-tag>
                <el-tag :type="statusType(srv.status)" size="small">{{ statusLabel(srv.status) }}</el-tag>
                <el-dropdown trigger="click" @command="(cmd) => onCommand(cmd, srv)">
                  <el-icon class="more-icon"><MoreFilled /></el-icon>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">编辑</el-dropdown-item>
                      <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
          </template>
          <div class="srv-meta">
            <span>IP: {{ srv.ip || '-' }}</span>
            <span>{{ srv.driver || '-' }} / CUDA {{ srv.cuda || '-' }}</span>
            <span>{{ interconnectLabel(srv.interconnect) }}</span>
          </div>
          <div v-if="srv.gpus.length === 0" class="empty">暂无 GPU</div>
          <div v-for="gpu in srv.gpus" :key="gpu.index" class="gpu-item">
            <div class="gpu-top">
              <span class="gpu-name">GPU{{ gpu.index }} · {{ gpu.name }}</span>
              <span class="gpu-temp">{{ gpu.temperature.toFixed(0) }}°C</span>
            </div>
            <div class="gpu-bar">
              <span class="bar-label">显存</span>
              <el-progress
                :percentage="vramPercent(gpu)"
                :color="barColor(vramPercent(gpu))"
                :stroke-width="10"
                class="gpu-progress"
              />
              <span class="bar-val">{{ (gpu.vram_used_mb / 1024).toFixed(1) }}/{{ (gpu.vram_total_mb / 1024).toFixed(1) }}G</span>
            </div>
            <div class="gpu-bar">
              <span class="bar-label">算力</span>
              <el-progress
                :percentage="gpu.utilization"
                :color="barColor(gpu.utilization)"
                :stroke-width="10"
                class="gpu-progress"
              />
              <span class="bar-val">{{ gpu.utilization.toFixed(0) }}%</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!loading && servers.length === 0" description="暂无节点，点击右上角「登记节点」手动登记，或在服务器上启动 Agent 自动注册" />

    <!-- 登记 / 编辑节点 -->
    <el-dialog v-model="nodeVisible" :title="editingId == null ? '登记节点' : '编辑节点'" width="640px">
      <el-form :model="nodeForm" label-width="90px">
        <el-form-item label="主机名" required>
          <el-input v-model="nodeForm.hostname" placeholder="如 gpu-node-01（唯一，用于 Agent 识别）" />
        </el-form-item>
        <el-form-item label="IP 地址">
          <el-input v-model="nodeForm.ip" placeholder="如 192.168.1.10" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="驱动">
              <el-input v-model="nodeForm.driver" placeholder="如 550.54.14" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="CUDA">
              <el-input v-model="nodeForm.cuda" placeholder="如 12.4" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="互联">
          <el-select v-model="nodeForm.interconnect" class="w-full">
            <el-option label="PCIe" value="pcie" />
            <el-option label="NVLink" value="nvlink" />
            <el-option label="InfiniBand" value="ib" />
          </el-select>
        </el-form-item>

        <el-form-item label="GPU 列表">
          <div class="gpu-editor">
            <div v-for="(g, i) in nodeForm.gpus" :key="i" class="gpu-row">
              <span class="gpu-idx">GPU{{ i }}</span>
              <el-select
                v-model="g.name"
                filterable
                allow-create
                default-first-option
                placeholder="选择或输入型号"
                class="gpu-name-select"
                @change="onGpuNameChange(g)"
              >
                <el-option v-for="p in gpuPresets" :key="p.name" :label="`${p.name} (${p.vram_gb}G)`" :value="p.name" />
              </el-select>
              <el-input-number v-model="g.vram_gb" :min="0" :step="2" controls-position="right" class="gpu-vram" />
              <span class="gpu-vram-unit">GB</span>
              <el-button text type="danger" @click="removeGpuRow(i)">移除</el-button>
            </div>
            <el-button size="small" @click="addGpuRow">+ 添加 GPU</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="nodeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitNode">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MoreFilled } from '@element-plus/icons-vue'
import { serversApi } from '../api'

defineOptions({ name: 'Dashboard' })

const servers = ref([])
const loading = ref(false)
const saving = ref(false)
const nodeVisible = ref(false)
const editingId = ref(null)
let timer = null

const nodeForm = reactive({ hostname: '', ip: '', driver: '', cuda: '', interconnect: 'pcie', gpus: [] })

const gpuPresets = [
  { name: 'RTX 4060 Ti', vram_gb: 16 },
  { name: 'RTX 4080', vram_gb: 16 },
  { name: 'RTX 4090', vram_gb: 24 },
  { name: 'RTX 3090', vram_gb: 24 },
  { name: 'A100', vram_gb: 40 },
  { name: 'A100 80GB', vram_gb: 80 },
  { name: 'A800', vram_gb: 80 },
  { name: 'H100', vram_gb: 80 },
  { name: 'H20', vram_gb: 96 },
  { name: 'V100', vram_gb: 32 },
  { name: 'L40S', vram_gb: 48 },
  { name: 'A6000', vram_gb: 48 },
  { name: 'A40', vram_gb: 48 },
]

const totalGpus = computed(() => servers.value.reduce((s, x) => s + (x.total_gpus || 0), 0))
const onlineCount = computed(() => servers.value.filter((s) => s.status === 'online').length)
const avgUtil = computed(() => {
  const gpus = servers.value.flatMap((s) => s.gpus || [])
  if (gpus.length === 0) return 0
  return gpus.reduce((s, g) => s + g.utilization, 0) / gpus.length
})

function vramPercent(gpu) {
  if (!gpu.vram_total_mb) return 0
  return Math.round((gpu.vram_used_mb / gpu.vram_total_mb) * 100)
}

function barColor(p) {
  if (p < 50) return '#67c23a'
  if (p < 80) return '#e6a23c'
  return '#f56c6c'
}

function statusType(status) {
  if (status === 'online') return 'success'
  if (status === 'degraded') return 'warning'
  return 'info'
}

function statusLabel(status) {
  return { online: '在线', offline: '离线', degraded: '降级' }[status] || status
}

function interconnectLabel(v) {
  return { pcie: 'PCIe', nvlink: 'NVLink', ib: 'InfiniBand' }[v] || v || '-'
}

async function load() {
  loading.value = true
  try {
    const resp = await serversApi.list()
    servers.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function openAdd() {
  editingId.value = null
  Object.assign(nodeForm, { hostname: '', ip: '', driver: '', cuda: '', interconnect: 'pcie', gpus: [] })
  nodeVisible.value = true
}

function openEdit(srv) {
  editingId.value = srv.id
  Object.assign(nodeForm, {
    hostname: srv.hostname,
    ip: srv.ip || '',
    driver: srv.driver || '',
    cuda: srv.cuda || '',
    interconnect: srv.interconnect || 'pcie',
    gpus: (srv.gpus || []).map((g) => ({ name: g.name, vram_gb: g.vram_total_mb ? Math.round(g.vram_total_mb / 1024) : 0 })),
  })
  nodeVisible.value = true
}

function onCommand(cmd, srv) {
  if (cmd === 'edit') openEdit(srv)
  else if (cmd === 'delete') removeNode(srv)
}

function addGpuRow() {
  nodeForm.gpus.push({ name: '', vram_gb: 0 })
}

function removeGpuRow(i) {
  nodeForm.gpus.splice(i, 1)
}

function onGpuNameChange(row) {
  const preset = gpuPresets.find((p) => p.name === row.name)
  if (preset) row.vram_gb = preset.vram_gb
}

async function submitNode() {
  if (!nodeForm.hostname.trim()) return ElMessage.warning('请输入主机名')
  const gpus = nodeForm.gpus
    .filter((g) => g.name)
    .map((g, i) => ({
      index: i,
      name: g.name,
      vram_total_mb: Math.round((g.vram_gb || 0) * 1024),
    }))
  const payload = {
    hostname: nodeForm.hostname.trim(),
    ip: nodeForm.ip || null,
    driver: nodeForm.driver || null,
    cuda: nodeForm.cuda || null,
    interconnect: nodeForm.interconnect,
    gpus,
  }
  saving.value = true
  try {
    if (editingId.value == null) {
      await serversApi.createManual(payload)
      ElMessage.success('节点已登记')
    } else {
      await serversApi.update(editingId.value, payload)
      ElMessage.success('节点已更新')
    }
    nodeVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function removeNode(srv) {
  try {
    await ElMessageBox.confirm(`确定删除节点「${srv.hostname}」吗？该操作不可恢复。`, '删除节点', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await serversApi.remove(srv.id)
    ElMessage.success('节点已删除')
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(() => {
  load()
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
.page-desc {
  color: #909399;
  font-size: 13px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
}
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.stat {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.stat .num {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}
.stat .label {
  color: #909399;
  font-size: 13px;
}
.srv-col {
  margin-bottom: 16px;
}
.srv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.srv-name {
  font-weight: 600;
}
.srv-badges {
  display: flex;
  align-items: center;
  gap: 8px;
}
.more-icon {
  cursor: pointer;
  color: #909399;
  outline: none;
}
.srv-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #909399;
  font-size: 12px;
  margin-bottom: 12px;
}
.empty {
  color: #c0c4cc;
  text-align: center;
  padding: 12px 0;
}
.gpu-item {
  padding: 8px 0;
  border-top: 1px solid #f0f0f0;
}
.gpu-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}
.gpu-name {
  font-size: 13px;
  color: #303133;
}
.gpu-temp {
  font-size: 12px;
  color: #e6a23c;
}
.gpu-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.bar-label {
  font-size: 12px;
  color: #909399;
  width: 28px;
}
.gpu-progress {
  flex: 1;
}
.bar-val {
  font-size: 12px;
  color: #606266;
  width: 80px;
  text-align: right;
}
.w-full {
  width: 100%;
}
.gpu-editor {
  width: 100%;
}
.gpu-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.gpu-idx {
  width: 48px;
  color: #909399;
  font-size: 13px;
  flex-shrink: 0;
}
.gpu-name-select {
  flex: 1;
}
.gpu-vram {
  width: 110px;
}
.gpu-vram-unit {
  color: #909399;
  font-size: 13px;
}
</style>
