import { defineStore } from 'pinia'
import { gameSocket } from '../ws/client'

const MEMORY_KEY = 'shabo.memory'

function revealKey(owner, slot) {
  return `${owner}:${slot}`
}

export const useGameStore = defineStore('game', {
  state: () => ({
    status: 'offline',
    room: null,
    game: null,
    invite: null,
    toast: '',
    toastTone: 'error',
    reveals: {},
    peeks: {},
    queue: [],
    now: Date.now(),
    started: false,
    offlineSince: 0,
    memoryAssist: localStorage.getItem(MEMORY_KEY) === '1'
  }),
  getters: {
    inRoom: (state) => Boolean(state.room),
    inGame: (state) => Boolean(state.game),
    remainSeconds: (state) => {
      if (!state.game || !state.game.deadline_ms) return 0
      return Math.max(0, Math.ceil((state.game.deadline_ms - state.now) / 1000))
    },
    disconnectedSeconds: (state) => {
      if (state.status === 'online' || !state.offlineSince) return 0
      return Math.floor((state.now - state.offlineSince) / 1000)
    }
  },
  actions: {
    start(token) {
      if (this.started) {
        gameSocket.send('sync')
        return
      }
      this.started = true

      gameSocket.on('status', (status) => {
        this.status = status
        if (status === 'online') {
          this.offlineSince = 0
        } else if (!this.offlineSince) {
          this.offlineSince = Date.now()
        }
      })
      gameSocket.on('message', (message) => this.handle(message))
      gameSocket.connect(token)

      setInterval(() => {
        this.now = Date.now()
        this.pruneReveals()
      }, 200)
    },
    stop() {
      gameSocket.close()
      this.started = false
      this.status = 'offline'
      this.room = null
      this.game = null
      this.reveals = {}
      this.peeks = {}
      this.queue = []
    },
    handle(message) {
      switch (message.type) {
        case 'authed':
          this.status = 'online'
          this.offlineSince = 0
          break
        case 'room_state':
          this.room = message.room
          this.game = message.game
          this.absorb(message.events || [])
          break
        case 'invite':
          this.invite = message
          break
        case 'notice':
          this.showToast(message.message, 'ok')
          break
        case 'error':
          this.showToast(message.message, 'error')
          break
        default:
          break
      }
    },
    absorb(events) {
      if (!events.length) return
      for (const event of events) {
        if (event.kind === 'reveal' && event.card) {
          this.reveals = {
            ...this.reveals,
            [revealKey(event.owner, event.slot)]: {
              card: event.card,
              owner: event.owner,
              slot: event.slot,
              until: Date.now() + (event.seconds || 3) * 1000
            }
          }
        }
        if (event.kind === 'peek') {
          this.peeks = {
            ...this.peeks,
            [revealKey(event.owner, event.slot)]: {
              viewer: event.viewer,
              owner: event.owner,
              slot: event.slot,
              until: Date.now() + (event.seconds || 3) * 1000
            }
          }
        }
      }
      this.queue = [...this.queue, ...events]
    },
    takeQueue() {
      const items = this.queue
      this.queue = []
      return items
    },
    pruneReveals() {
      const now = Date.now()
      let changed = false
      const next = {}
      for (const [key, item] of Object.entries(this.reveals)) {
        if (item.until > now) {
          next[key] = item
        } else {
          changed = true
        }
      }
      if (changed) this.reveals = next
      let peekChanged = false
      const nextPeeks = {}
      for (const [key, item] of Object.entries(this.peeks)) {
        if (item.until > now) {
          nextPeeks[key] = item
        } else {
          peekChanged = true
        }
      }
      if (peekChanged) this.peeks = nextPeeks
    },
    revealedCard(owner, slot) {
      const item = this.reveals[revealKey(owner, slot)]
      return item ? item.card : null
    },
    peekedSlot(owner, slot) {
      return Boolean(this.peeks[revealKey(owner, slot)])
    },
    activeReveal() {
      const list = Object.values(this.reveals)
      return list.length ? list[list.length - 1] : null
    },
    toggleMemory() {
      this.memoryAssist = !this.memoryAssist
      localStorage.setItem(MEMORY_KEY, this.memoryAssist ? '1' : '0')
    },
    showToast(text, tone = 'error') {
      this.toast = text
      this.toastTone = tone
      setTimeout(() => {
        if (this.toast === text) this.toast = ''
      }, 2200)
    },
    send(type, payload) {
      gameSocket.send(type, payload)
    },
    respondInvite(accept) {
      if (this.invite) {
        gameSocket.send('invite_response', { code: this.invite.code, accept })
      }
      this.invite = null
    }
  }
})
