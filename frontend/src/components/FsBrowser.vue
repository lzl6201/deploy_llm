<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="680px"
    @update:model-value="$emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <div class="fs-browser">
      <div class="fs-toolbar">
        <el-button size="small" :disabled="!canUp" @click="goUp">
          <el-icon><Back /></el-icon>
          <span>上一级</span>
        </el-button>
        <el-input :model-value="current" readonly size="small" class="fs-path" />
        <el-button size="small" @click="load(current)">刷新</el-button>
      </div>

      <el-table
        :data="entries"
        size="small"
        height="360"
        highlight-current-row
        v-loading="loading"
        @row-dblclick="onDblClick"
        @row-click="onRowClick"
      >
        <el-table-column label="名称" min-width="260">
          <template #default="{ row }">
            <el-icon v-if="row.type === 'dir'" class="icon-dir"><Folder /></el-icon>
            <el-icon v-else-if="row.is_gguf" class="icon-gguf"><Document /></el-icon>
            <el-icon v-else class="icon-file"><Tickets /></el-icon>
            <span :class="{ 'name-dir': row.type === 'dir' }">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ row.type === 'dir' ? '目录' : '文件' }}</template>
        </el-table-column>
        <el-table-column label="大小" width="110">
          <template #default="{ row }">{{ row.type === 'dir' ? '-' : fmtSize(row.size_bytes) }}</template>
        </el-table-column>
      </el-table>
    </div>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button v-if="allowDir" @click="confirmDir">选择当前目录</el-button>
      <el-button type="primary" :disabled="!selected" @click="confirm">选择</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Folder, Document, Tickets, Back } from '@element-plus/icons-vue'
import { fsApi } from '../api'

const props = defineProps({
  modelValue: Boolean,
  title: { type: String, default: '选择路径' },
  allowDir: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'select'])

const current = ref('')
const entries = ref([])
const selected = ref('')
const loading = ref(false)

const canUp = computed(() => {
  const roots = rootList.value
  if (!current.value || roots.length === 0) return false
  return !roots.some((r) => r === current.value)
})
const rootList = ref([])

async function onOpen() {
  selected.value = ''
  if (!current.value) {
    try {
      const resp = await fsApi.roots()
      rootList.value = resp.data.filter((r) => r.exists).map((r) => r.path)
      if (rootList.value.length > 0) {
        await load(rootList.value[0])
      } else {
        ElMessage.warning('未配置可访问的存储根目录，请设置 ALLOWED_FS_ROOTS')
      }
    } catch (e) {
      ElMessage.error(e.message)
    }
  } else {
    await load(current.value)
  }
}

async function load(path) {
  loading.value = true
  try {
    const resp = await fsApi.list(path)
    current.value = resp.data.path
    entries.value = resp.data.entries
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function goUp() {
  if (!canUp.value) return
  const idx = current.value.replace(/[\\/]+$/, '')
  const sep = idx.includes('\\') ? '\\' : '/'
  const parent = idx.split(sep).slice(0, -1).join(sep) || idx
  if (parent === current.value) return
  await load(parent)
}

function onRowClick(row) {
  selected.value = row.path
}

function onDblClick(row) {
  if (row.type === 'dir') {
    selected.value = ''
    load(row.path)
  } else {
    selected.value = row.path
    confirm()
  }
}

function confirm() {
  if (!selected.value) return
  emit('select', selected.value)
  emit('update:modelValue', false)
}

function confirmDir() {
  if (!current.value) return
  emit('select', current.value)
  emit('update:modelValue', false)
}

function fmtSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let n = bytes
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i++
  }
  return `${n.toFixed(1)} ${units[i]}`
}
</script>

<style scoped>
.fs-browser {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.fs-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}
.fs-path {
  flex: 1;
}
.icon-dir {
  color: #e6a23c;
  margin-right: 4px;
}
.icon-gguf {
  color: #409eff;
  margin-right: 4px;
}
.icon-file {
  color: #c0c4cc;
  margin-right: 4px;
}
.name-dir {
  font-weight: 500;
}
</style>
