<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">大模型部署平台</div>
      <el-menu :default-active="activeMenu" router background-color="#001529" text-color="#a6adb4" active-text-color="#ffffff">
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
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="page-title">{{ $route.meta.title }}</span>
      </el-header>
      <el-main class="main">
        <keep-alive include="Recommend,Models">
          <router-view />
        </keep-alive>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style scoped>
.layout {
  height: 100%;
}
.aside {
  background-color: #001529;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}
.aside :deep(.el-menu) {
  border-right: none;
}
.header {
  display: flex;
  align-items: center;
  border-bottom: 1px solid #e6e6e6;
  background: #fff;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
}
.main {
  background: #f5f7fa;
}
</style>
