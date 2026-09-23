import { defineStore } from 'pinia'
import { getToken, request, setToken } from '../api/http'

const USER_KEY = 'shabo.user'

function loadUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (error) {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getToken(),
    user: loadUser(),
    avatars: []
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token && state.user),
    myId: (state) => (state.user ? state.user.user_id : '')
  },
  actions: {
    persist() {
      setToken(this.token)
      if (this.user) {
        localStorage.setItem(USER_KEY, JSON.stringify(this.user))
      } else {
        localStorage.removeItem(USER_KEY)
      }
    },
    async register(payload) {
      const data = await request('/api/auth/register', { method: 'POST', body: payload, auth: false })
      this.token = data.access_token
      this.user = data.user
      this.persist()
    },
    async login(payload) {
      const data = await request('/api/auth/login', { method: 'POST', body: payload, auth: false })
      this.token = data.access_token
      this.user = data.user
      this.persist()
    },
    async refresh() {
      this.user = await request('/api/auth/me')
      this.persist()
    },
    async loadAvatars() {
      if (this.avatars.length) return
      const data = await request('/api/avatars', { auth: false })
      this.avatars = data.avatars
    },
    async updateProfile(payload) {
      this.user = await request('/api/users/me', { method: 'PUT', body: payload })
      this.persist()
    },
    async fetchStats(userId) {
      return request(`/api/users/${userId}/stats`)
    },
    async fetchLeaderboard() {
      return request('/api/leaderboard')
    },
    logout() {
      this.token = ''
      this.user = null
      this.persist()
    }
  }
})
