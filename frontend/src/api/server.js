const STORAGE_KEY = 'shabo.server'

function normalize(input) {
  const value = (input || '').trim().replace(/\/+$/, '')
  if (!value) return ''
  if (/^https?:\/\//i.test(value)) return value
  const scheme = window.location.protocol === 'https:' ? 'https://' : 'http://'
  return scheme + value
}

export function getServerSetting() {
  return localStorage.getItem(STORAGE_KEY) || ''
}

export function setServerSetting(input) {
  const value = normalize(input)
  if (value) {
    localStorage.setItem(STORAGE_KEY, value)
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
  return value
}

export function httpBase() {
  return getServerSetting() || window.location.origin
}

export function wsUrl() {
  return httpBase().replace(/^http/i, 'ws') + '/ws'
}

export function serverLabel() {
  return getServerSetting() || '当前站点（默认）'
}
