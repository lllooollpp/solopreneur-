import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue')
    },
    {
      path: '/accounts',
      name: 'accounts',
      component: () => import('@/views/AccountPoolView.vue')
    },
    {
      path: '/config',
      name: 'config',
      component: () => import('@/views/ConfigView.vue')
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue')
    },
    {
      path: '/flow',
      name: 'flow',
      component: () => import('@/views/FlowView.vue')
    }
  ]
})

export default router
