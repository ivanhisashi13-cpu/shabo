import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../store/auth'

const routes = [
  { path: '/', redirect: '/hall' },
  { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
  { path: '/hall', name: 'hall', component: () => import('../views/Hall.vue') },
  { path: '/game', name: 'game', component: () => import('../views/Game.vue') },
  { path: '/rules', name: 'rules', component: () => import('../views/Rules.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/hall' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.name !== 'login' && to.name !== 'rules' && !auth.isLoggedIn) return { name: 'login' }
  if (to.name === 'login' && auth.isLoggedIn) return { name: 'hall' }
  return true
})

export default router
