<template>
  <div>
    <div class="toolbar">
      <span class="page-desc">聚合节点 GPU 指标与部署状态，自动评估告警规则；条件解除后告警自动恢复。</span>
      <div class="toolbar-actions">
        <el-button @click="load" :loading="loading">刷新</el-button>
      </div>
    </div>

    <div class="stat-row">
      <div class="telemetry">
        <span class="t-label">在线节点</span>
        <span class="t-value mono accent">{{ overview.nodes_online }}<span class="unit">/{{ overview.nodes_total }}</span></span>
      </div>
      <div class="telemetry">
        <span class="t-label">GPU 总数</span>
        <span class="t-value mono">{{ overview.gpus_total }}</span>
      </div>
      <div class="telemetry">
        <span class="t-label">运行实例</span>
        <span class="t-value mono">{{ overview.running_deployments }}</span>
      </div>
      <div class="telemetry">
        <span class="t-label">显存使用</span>
        <span class="t-value mono">{{ vramUsedGb }}<span class="unit">/{{ vramTotalGb }} GB</span></span>
      </div>
    </div>

    <el-card class="alert-card">
      <template #header>
        <div class="card-header">
          <span class="title">告警</span>
          <div class="header-actions">
            <el-radio-group v-model="openOnly" size="small" @change="loadAlerts">
              <el-radio-button :value="true">未处理</el-radio-button>
              <el-radio-button :value="false">全部</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>

      <div v-if="overview.open_alerts" class="severity-summary">
        <el-tag v-if="overview.alerts_by_severity?.critical" type="danger" size="small">
          严重 {{ overview.alerts_by_severity.critical }}
        </el-tag>
        <el-tag v-if="overview.alerts_by_severity?.warning" type="warning" size="small">
          警告 {{ overview.alerts_by_severity.warning }}
        </el-tag>
        <el-tag v-if="overview.alerts_by_severity?.info" type="info" size="small">
          提示 {{ overview.alerts_by_severity.info }}
        </el-tag>
      </div>

      <el-table :data="alerts" v-loading="loading" size="small" max-height="560">
        <el-table-column label="级别" width="90">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">{{ typeLabel(row.type) }}</template>
        </el-table-column>
        <el-table-column prop="message" label="内容" min-width="320" show-overflow-tooltip />
        <el-table-column label="节点" width="110">
          <template #default="{ row }">{{ row.server_id ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button v-if="row.status === 'open'" size="small" text type="primary" @click="ack(row)">处理</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && alerts.length === 0" description="暂无告警" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onActivated, onDeactivated, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { monitorApi } from '../api'

defineOptions({ name: 'Monitor' })

const overview = ref({
  nodes_total: 0,
  nodes_online: 0,
  gpus_total: 0,
  vram_used_mb: 0,
  vram_total_mb: 0,
  running_deployments: 0,
  open_alerts: 0,
  alerts_by_severity: {},
})
const alerts = ref([])
const loading = ref(false)
const openOnly = ref(true)
let timer = null

const vramUsedGb = computed(() => ((overview.value.vram_used_mb || 0) / 1024).toFixed(0))
const vramTotalGb = computed(() => ((overview.value.vram_total_mb || 0) / 1024).toFixed(0))

async function load() {
  loading.value = true
  try {
    const [o, a] = await Promise.all([monitorApi.overview(), monitorApi.alerts(openOnly.value)])
    overview.value = o.data
    alerts.value = a.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function loadAlerts() {
  try {
    const resp = await monitorApi.alerts(openOnly.value)
    alerts.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function ack(row) {
  try {
    await monitorApi.ack(row.id)
    ElMessage.success('已处理')
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function severityType(s) {
  return { critical: 'danger', warning: 'warning', info: 'info' }[s] || 'info'
}

function severityLabel(s) {
  return { critical: '严重', warning: '警告', info: '提示' }[s] || s
}

function typeLabel(t) {
  return {
    heartbeat_lost: '心跳丢失',
    gpu_vram_high: '显存过高',
    gpu_temp_high: '温度过高',
    gpu_idle: '利用率低',
    deploy_oom: '部署 OOM',
    deploy_failed: '部署失败',
  }[t] || t
}

function statusType(s) {
  return s === 'open' ? 'danger' : 'success'
}

function statusLabel(s) {
  return s === 'open' ? '未处理' : '已解决'
}

function fmtTime(ts) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString()
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
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}
.header-actions {
  display: flex;
  gap: 8px;
}
.severity-summary {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
</style>
