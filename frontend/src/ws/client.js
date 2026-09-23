import { wsUrl } from '../api/server'

const RECONNECT_DELAY_MS = 1500
const HEARTBEAT_MS = 15000

export class GameSocket {
  constructor() {
    this.socket = null
    this.token = ''
    this.handlers = new Map()
    this.reconnectTimer = null
    this.heartbeatTimer = null
    this.closedByUser = false
  }

  on(type, handler) {
    this.handlers.set(type, handler)
  }

  emit(type, payload) {
    const handler = this.handlers.get(type)
    if (handler) handler(payload)
  }

  connect(token) {
    this.token = token
    this.closedByUser = false
    this.open()
  }

  open() {
    if (this.socket && (this.socket.readyState === 0 || this.socket.readyState === 1)) return

    let socket
    try {
      socket = new WebSocket(wsUrl())
    } catch (error) {
      this.scheduleReconnect()
      return
    }
    this.socket = socket
    this.emit('status', 'connecting')

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'auth', token: this.token }))
      this.startHeartbeat()
    }

    socket.onmessage = (event) => {
      let message
      try {
        message = JSON.parse(event.data)
      } catch (error) {
        return
      }
      if (message.type === 'ping' || message.type === 'pong') return
      this.emit('message', message)
    }

    socket.onclose = (event) => {
      this.stopHeartbeat()
      this.emit('status', 'offline')
      if (event && event.code === 4001) {
        this.closedByUser = true
        this.emit('message', { type: 'error', message: '该账号已在其他设备登录，请勿多处同时登录' })
        return
      }
      if (!this.closedByUser) this.scheduleReconnect()
    }

    socket.onerror = () => {
      this.emit('status', 'offline')
    }
  }

  startHeartbeat() {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (this.socket && this.socket.readyState === 1) {
        this.socket.send(JSON.stringify({ type: 'ping' }))
      }
    }, HEARTBEAT_MS)
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer)
    this.heartbeatTimer = null
  }

  scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = setTimeout(() => this.open(), RECONNECT_DELAY_MS)
  }

  send(type, payload = {}) {
    if (!this.socket || this.socket.readyState !== 1) {
      this.emit('message', { type: 'error', message: '连接已断开，正在重连…' })
      return
    }
    this.socket.send(JSON.stringify({ type, ...payload }))
  }

  close() {
    this.closedByUser = true
    this.stopHeartbeat()
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    if (this.socket) this.socket.close()
    this.socket = null
  }
}

export const gameSocket = new GameSocket()
