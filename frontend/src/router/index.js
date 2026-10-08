import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layout/MainLayout.vue'
import { getRole, isLoggedIn } from '../auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', redirect: '/dashboard' },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { title: '节点总览' },
      },
      {
        path: 'models',
        name: 'Models',
        component: () => import('../views/Models.vue'),
        meta: { title: '模型仓库' },
      },
      {
        path: 'recommend',
        name: 'Recommend',
        component: () => import('../views/Recommend.vue'),
        meta: { title: '智能推荐' },
      },
      {
        path: 'deploy',
        name: 'Deploy',
        component: () => import('../views/Deploy.vue'),
        meta: { title: '一键部署' },
      },
      {
        path: 'deployments',
        name: 'Deployments',
        component: () => import('../views/Deployments.vue'),
        meta: { title: '部署管理' },
      },
      {
        path: 'quantize',
        name: 'Quantize',
        component: () => import('../views/Quantize.vue'),
        meta: { title: '模型量化' },
      },
      {
        path: 'monitor',
        name: 'Monitor',
        component: () => import('../views/Monitor.vue'),
        meta: { title: '监控告警' },
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('../views/Users.vue'),
        meta: { title: '用户管理', roles: ['admin'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const loggedIn = isLoggedIn()
  if (to.path === '/login') {
    return loggedIn ? '/dashboard' : true
  }
  if (!loggedIn) return '/login'
  if (to.meta.roles && !to.meta.roles.includes(getRole())) {
    return '/dashboard'
  }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - 大模型部署平台` : '大模型部署平台'
})

export default router
