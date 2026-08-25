<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <span class="title">部署管理</span>
        <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>

      <el-table :data="deployments" v-loading="loading" row-key="id">
        <el-table-column prop="name" label="部署名" min-width="180" />
        <el-table-column prop="engine" label="引擎" width="90" />
        <el-table-column prop="server_id" label="服务器" width="90" />
        <el-table-column label="GPU" width="110">
          <template #default="{ row }">{{ (row.gpu_ids || []).join(',') }}</template>
        </el-table-column>
        <el-table-column prop="tp_size" label="TP" width="70" />
        <el-table-column prop="port" label="端口" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="endpoint" label="访问地址" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'running'"
              type="danger"
              size="small"
              plain
              @click="stop(row)"
            >
              停止
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deploymentsApi } from '../api'

const deployments = ref([])
const loading = ref(false)
let timer = null

function statusType(status) {
  if (status === 'running') return 'success'
  if (status === 'pending' || status === 'pulling' || status === 'launching' || status === 'health_checking')
    return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const resp = await deploymentsApi.list()
    deployments.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function stop(row) {
  try {
    await ElMessageBox.confirm(`确认停止部署「${row.name}」？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deploymentsApi.stop(row.id)
    ElMessage.success('已发送停止指令')
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, 8000)
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
</style>
