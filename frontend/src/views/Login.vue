<template>
  <div class="login">
    <div class="login-card">
      <div class="brand">
        <div class="logo-mark" aria-hidden="true">
          <span class="cell on" />
          <span class="cell" />
          <span class="cell" />
          <span class="cell on" />
        </div>
        <div class="brand-text">
          <div class="brand-title">大模型部署平台</div>
          <div class="brand-sub mono">GPU OPS CONSOLE</div>
        </div>
      </div>

      <el-form :model="form" @keyup.enter="submit">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large" autocomplete="username">
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            autocomplete="current-password"
          >
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="submit">
          登录
        </el-button>
      </el-form>

      <div class="login-foot mono">MASTER · CONTROL PLANE</div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '../api'
import { setToken, setUser } from '../auth'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function submit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const resp = await authApi.login({ username: form.username, password: form.password })
    setToken(resp.data.access_token)
    setUser(resp.data.user)
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(1200px 600px at 50% -10%, rgba(245, 166, 35, 0.08), transparent 60%),
    var(--bg);
}
.login-card {
  width: 360px;
  padding: 36px 32px 24px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}
.logo-mark {
  display: grid;
  grid-template-columns: repeat(2, 9px);
  grid-template-rows: repeat(2, 9px);
  gap: 3px;
  flex-shrink: 0;
}
.logo-mark .cell {
  background: var(--accent);
  border-radius: 2px;
  opacity: 0.22;
}
.logo-mark .cell.on {
  opacity: 1;
  box-shadow: 0 0 8px rgba(245, 166, 35, 0.7);
}
.brand-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}
.brand-sub {
  font-size: 10px;
  color: var(--text-3);
  letter-spacing: 0.14em;
  margin-top: 3px;
}
.login-btn {
  width: 100%;
  margin-top: 4px;
}
.login-foot {
  margin-top: 24px;
  text-align: center;
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--text-3);
}
</style>
