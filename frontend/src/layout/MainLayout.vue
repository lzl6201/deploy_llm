<template>
  <el-container class="layout">
    <el-aside width="224px" class="aside">
      <div class="logo">
        <div class="logo-mark" aria-hidden="true">
          <span class="cell on" />
          <span class="cell" />
          <span class="cell" />
          <span class="cell on" />
        </div>
        <div class="logo-text">
          <div class="logo-title">大模型部署平台</div>
          <div class="logo-sub mono">GPU OPS CONSOLE</div>
        </div>
      </div>

      <el-menu :default-active="activeMenu" router class="nav">
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <span>节点总览</span>
        </el-menu-item>
        <el-menu-item index="/models">
          <el-icon><Files /></el-icon>
          <span>模型仓库</span>
        </el-menu-item>
        <el-menu-item index="/recommend">
          <el-icon><Compass /></el-icon>
          <span>智能推荐</span>
        </el-menu-item>
        <el-menu-item index="/deploy">
          <el-icon><VideoPlay /></el-icon>
          <span>一键部署</span>
        </el-menu-item>
        <el-menu-item index="/deployments">
          <el-icon><List /></el-icon>
          <span>部署管理</span>
        </el-menu-item>
        <el-menu-item index="/quantize">
          <el-icon><Filter /></el-icon>
          <span>模型量化</span>
        </el-menu-item>
        <el-menu-item index="/monitor">
          <el-icon><Bell /></el-icon>
          <span>监控告警</span>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/users">
          <el-icon><Setting /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>

      <div class="aside-foot mono">MASTER · v0.2.0</div>
    </el-aside>

    <el-container class="body">
      <el-header class="header">
        <div class="header-title">
          <span class="eyebrow mono">//</span>
          <span class="page-title">{{ $route.meta.title }}</span>
        </div>
        <el-dropdown trigger="click" @command="onUserCommand">
          <div class="user-chip">
            <el-icon><UserFilled /></el-icon>
            <span class="user-name">{{ user?.username }}</span>
            <el-tag size="small" :type="roleType">{{ roleLabel }}</el-tag>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>{{ roleLabel }} · {{ user?.username }}</el-dropdown-item>
              <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main">
        <keep-alive>
          <router-view />
        </keep-alive>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearAuth, getUser } from '../auth'

const route = useRoute()
const router = useRouter()
const activeMenu = computed(() => route.path)

const user = computed(() => getUser())
const isAdmin = computed(() => user.value?.role === 'admin')
const roleLabel = computed(
  () => ({ admin: '管理员', operator: '运维', viewer: '只读' }[user.value?.role] || user.value?.role || '')
)
const roleType = computed(
  () => ({ admin: 'danger', operator: 'warning', viewer: 'info' }[user.value?.role] || 'info')
)

function onUserCommand(cmd) {
  if (cmd === 'logout') {
    clearAuth()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout {
  height: 100%;
}

.aside {
  display: flex;
  flex-direction: column;
  background-color: var(--surface);
  border-right: 1px solid var(--border);
}

/* 品牌区 */
.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
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
.logo-text {
  line-height: 1.2;
}
.logo-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: 0.01em;
}
.logo-sub {
  font-size: 10px;
  color: var(--text-3);
  letter-spacing: 0.14em;
  margin-top: 3px;
}

/* 导航 */
.nav {
  flex: 1;
  padding: 12px 10px;
  border-right: none;
  background: transparent;
}
.nav :deep(.el-menu-item) {
  position: relative;
  height: 44px;
  line-height: 44px;
  margin: 2px 0;
  border-radius: 8px;
  color: var(--text-2);
  font-size: 14px;
}
.nav :deep(.el-menu-item:hover) {
  background: var(--surface-2);
  color: var(--text);
}
.nav :deep(.el-menu-item.is-active) {
  background: rgba(245, 166, 35, 0.1);
  color: var(--accent-hi);
  font-weight: 600;
}
.nav :deep(.el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  border-radius: 0 3px 3px 0;
  background: var(--accent);
  box-shadow: 0 0 8px rgba(245, 166, 35, 0.8);
}

.aside-foot {
  padding: 14px 22px;
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--text-3);
  border-top: 1px solid var(--border);
}

.body {
  min-width: 0;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  padding: 0 24px;
}
.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.eyebrow {
  color: var(--accent);
  font-size: 16px;
}
.page-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: 0.01em;
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--text-2);
  outline: none;
}
.user-name {
  font-size: 13px;
  color: var(--text);
}

.main {
  background: transparent;
  padding: 24px;
}
</style>
