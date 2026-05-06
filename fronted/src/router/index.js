import { createRouter, createWebHistory } from 'vue-router'

const LoginRoutePlaceholder = { template: '<div />' }

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginRoutePlaceholder,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/tasks',
    name: 'TaskList',
    component: () => import('../views/TaskList.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/agent',
    name: 'AgentChat',
    component: () => import('../views/AgentChat.vue'),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const userStr = localStorage.getItem('user')
  let isAuthenticated = false
  
  if (userStr) {
    try {
      const user = JSON.parse(userStr)
      isAuthenticated = !!user.userId
    } catch {
      localStorage.removeItem('user')
    }
  }

  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && isAuthenticated) {
    next('/')
  } else {
    next()
  }
})

export default router
