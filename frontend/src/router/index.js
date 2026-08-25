import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layout/MainLayout.vue'

const routes = [
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
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - 大模型部署平台` : '大模型部署平台'
})

export default router
