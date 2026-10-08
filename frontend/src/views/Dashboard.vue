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
      <div class="telemetry">
        <span class="t-label">服务器</span>
        <span class="t-value mono">{{ servers.length }}</span>
      </div>
      <div class="telemetry">
        <span class="t-label">GPU 总数</span>
        <span class="t-value mono">{{ totalGpus }}</span>
      </div>
      <div class="telemetry">
        <span class="t-label">在线节点</span>
        <span class="t-value mono accent">{{ onlineCount }}</span>
      </div>
      <div class="telemetry">
        <span class="t-label">平均利用率</span>
        <span class="t-value mono">{{ avgUtil.toFixed(1) }}<span class="unit">%</span></span>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col v-for="srv in servers" :key="srv.id" :xs="24" :sm="12" :lg="8" class="srv-col">
        <el-card class="srv-card">
          <template #header>
            <div class="srv-header">
              <div class="srv-id">
                <span class="srv-name">{{ srv.hostname }}</span>
                <span class="srv-ip mono">{{ srv.ip || '—' }}</span>
              </div>
              <div class="srv-badges">
                <el-tag v-if="srv.source === 'manual'" size="small" type="info">手动登记</el-tag>
                <span class="status-dot" :class="'dot-' + statusDot(srv.status)" />
                <span class="status-text">{{ statusLabel(srv.status) }}</span>
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

          <div class="srv-meta mono">
            <span>{{ srv.driver || '—' }}</span>
            <span>CUDA {{ srv.cuda || '—' }}</span>
            <span>{{ interconnectLabel(srv.interconnect) }}</span>
          </div>

          <div v-if="srv.gpus.length === 0" class="empty">暂无 GPU</div>
          <div v-for="gpu in srv.gpus" :key="gpu.index" class="gpu-item">
            <div class="gpu-top">
              <span class="gpu-name">GPU{{ gpu.index }} · {{ gpu.name }}</span>
              <span class="gpu-temp mono" :class="'t-' + tempClass(gpu.temperature)">
                {{ gpu.temperature.toFixed(0) }}°C
              </span>
            </div>

            <div class="metric-row">
              <span class="row-label">显存</span>
              <div class="mem-map" :class="'m-' + vramClass(vramPercent(gpu))">
                <span
                  v-for="i in 40"
                  :key="i"
                  class="mem-cell"
                  :class="{ filled: i <= filledCells(vramPercent(gpu)) }"
                />
              </div>
              <span class="row-val mono">
                {{ (gpu.vram_used_mb / 1024).toFixed(1) }}/{{ (gpu.vram_total_mb / 1024).toFixed(1) }}G
              </span>
            </div>

            <div class="metric-row">
              <span class="row-label">算力</span>
              <div class="util-track">
                <div class="util-fill" :class="'u-' + utilClass(gpu.utilization)" :style="{ width: gpu.utilization + '%' }" />
              </div>
              <span class="row-val mono">{{ gpu.utilization.toFixed(0) }}%</span>
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
import { computed, onActivated, onDeactivated, onMounted, onUnmounted, reactive, ref } from 'vue'
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

function filledCells(p) {
  return Math.round((p / 100) * 40)
}

function vramClass(p) {
  if (p < 50) return 'ok'
  if (p < 85) return 'warn'
  return 'danger'
}

function utilClass(u) {
  if (u < 50) return 'ok'
  if (u < 85) return 'warn'
  return 'danger'
}

function tempClass(t) {
  if (t < 70) return 'ok'
  if (t < 85) return 'warn'
  return 'danger'
}

function statusDot(status) {
  if (status === 'online') return 'ok'
  if (status === 'degraded') return 'warn'
  return 'off'
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

function startPolling() {
  stopPolling()
  load()
  timer = setInterval(load, 5000)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(startPolling)
onActivated(startPolling)
onDeactivated(stopPolling)
onUnmounted(stopPolling)
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}
.page-desc {
  color: var(--text-2);
  font-size: 13px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
}

/* 遥测条 */
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 18px;
}
.telemetry {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
}
.t-label {
  font-size: 12px;
  color: var(--text-3);
  letter-spacing: 0.02em;
}
.t-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text);
  line-height: 1;
}
.t-value.accent {
  color: var(--accent-hi);
}
.t-value .unit {
  font-size: 15px;
  color: var(--text-3);
  font-weight: 500;
  margin-left: 2px;
}

.srv-col {
  margin-bottom: 16px;
}
.srv-card {
  transition: border-color 0.2s ease;
}
.srv-card:hover {
  border-color: var(--border-strong);
}
.srv-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}
.srv-id {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.srv-name {
  font-weight: 600;
  color: var(--text);
}
.srv-ip {
  font-size: 12px;
  color: var(--text-3);
}
.srv-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.dot-ok {
  background: var(--ok);
  box-shadow: 0 0 8px rgba(52, 211, 153, 0.8);
}
.status-dot.dot-warn {
  background: var(--warn);
  box-shadow: 0 0 8px rgba(251, 191, 36, 0.8);
}
.status-dot.dot-off {
  background: var(--text-3);
}
.status-text {
  font-size: 12px;
  color: var(--text-2);
}
.more-icon {
  cursor: pointer;
  color: var(--text-3);
  outline: none;
}
.srv-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 11px;
  color: var(--text-3);
  margin-bottom: 8px;
}
.empty {
  color: var(--text-3);
  text-align: center;
  padding: 12px 0;
}

.gpu-item {
  padding: 10px 0;
  border-top: 1px solid var(--border);
}
.gpu-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 10px;
}
.gpu-name {
  font-size: 13px;
  color: var(--text);
  font-weight: 500;
}
.gpu-temp {
  font-size: 12px;
}
.gpu-temp.t-ok { color: var(--ok); }
.gpu-temp.t-warn { color: var(--warn); }
.gpu-temp.t-danger { color: var(--danger); }

.metric-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
.row-label {
  font-size: 11px;
  color: var(--text-3);
  width: 26px;
  flex-shrink: 0;
}
.row-val {
  font-size: 12px;
  color: var(--text-2);
  width: 108px;
  text-align: right;
  flex-shrink: 0;
}

/* 显存「内存映射」分段条 — 签名元素 */
.mem-map {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(40, 1fr);
  gap: 2px;
  height: 14px;
}
.mem-cell {
  border-radius: 1px;
  background: var(--surface-3);
}
.mem-cell.filled {
  background: var(--info);
}
.mem-map.m-ok .mem-cell.filled { background: var(--ok); }
.mem-map.m-warn .mem-cell.filled { background: var(--warn); }
.mem-map.m-danger .mem-cell.filled { background: var(--danger); }

.util-track {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--surface-3);
  overflow: hidden;
}
.util-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--info);
  transition: width 0.4s ease;
}
.util-fill.u-ok { background: var(--ok); }
.util-fill.u-warn { background: var(--warn); }
.util-fill.u-danger { background: var(--danger); }

.w-full {
  width: 100%;
}
.gpu-editor {
  width: 100%;
}
.gpu-editor .gpu-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
}
.gpu-idx {
  width: 48px;
  color: var(--text-3);
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
  color: var(--text-3);
  font-size: 13px;
}
</style>
