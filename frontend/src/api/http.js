import { httpBase } from './server'

const TOKEN_KEY = 'shabo.token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

export async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth && getToken()) headers.Authorization = `Bearer ${getToken()}`

  let response
  try {
    response = await fetch(httpBase() + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body)
    })
  } catch (error) {
    throw new Error('无法连接服务器，请检查服务器地址')
  }

  const text = await response.text()
  const data = text ? JSON.parse(text) : null
  if (!response.ok) {
    const detail = data && data.detail
    if (Array.isArray(detail)) throw new Error(detail[0]?.msg || '请求失败')
    throw new Error(detail || '请求失败')
  }
  return data
}
