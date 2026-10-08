<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <span class="title">用户管理</span>
        <el-button type="primary" @click="openCreate">新建用户</el-button>
      </div>

      <el-table :data="users" v-loading="loading" row-key="id">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="160" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="roleType(row.role)" size="small">{{ roleLabel(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" text type="danger" :disabled="row.username === currentUsername" @click="remove(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="新建用户" width="440px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" class="w-full">
            <el-option label="管理员 (admin)" value="admin" />
            <el-option label="运维 (operator)" value="operator" />
            <el-option label="只读 (viewer)" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { authApi } from '../api'
import { getUser } from '../auth'

const users = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const form = reactive({ username: '', password: '', role: 'viewer' })

const currentUsername = ref(getUser()?.username || '')

function roleType(role) {
  return { admin: 'danger', operator: 'warning', viewer: 'info' }[role] || 'info'
}

function roleLabel(role) {
  return { admin: '管理员', operator: '运维', viewer: '只读' }[role] || role
}

function fmtTime(ts) {
  return ts ? new Date(ts).toLocaleString() : '-'
}

async function load() {
  loading.value = true
  try {
    const resp = await authApi.users()
    users.value = resp.data
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, { username: '', password: '', role: 'viewer' })
  dialogVisible.value = true
}

async function submit() {
  if (!form.username.trim()) return ElMessage.warning('请输入用户名')
  if (!form.password || form.password.length < 6) return ElMessage.warning('密码至少 6 位')
  saving.value = true
  try {
    await authApi.createUser({ username: form.username.trim(), password: form.password, role: form.role })
    ElMessage.success('用户已创建')
    dialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户「${row.username}」吗？`, '删除用户', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await authApi.removeUser(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(load)
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
  font-weight: 700;
  color: var(--text);
}
.w-full {
  width: 100%;
}
</style>
