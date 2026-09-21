import axios from 'axios'
import { getAccess, getRefresh, saveSession, clearSession, decodeToken } from './session.js'

const api = axios.create({ baseURL: import.meta.env?.VITE_API_URL || 'http://localhost:8000/api' })
let refreshing = null

export function refreshSession() {
  if (refreshing) return refreshing
  const initial = getRefresh()
  if (!initial) return Promise.reject(new Error('Sesión no disponible'))
  const perform = async () => {
    // A different tab may have rotated the token while we awaited its lock.
    const current = getRefresh()
    if (!current) throw new Error('Sesión cerrada')
    if (current !== initial) return getAccess()
    const { data } = await axios.post(`${api.defaults.baseURL}/token/refresh/`, { refresh: current })
    // Never resurrect a session after logout or a newer login.
    if (getRefresh() !== current) throw new Error('La sesión cambió')
    saveSession(data)
    return data.access
  }
  refreshing = (navigator.locks?.request
    ? navigator.locks.request('neorx-token-refresh', perform)
    : perform())
    .catch(error => {
      if ([400, 401, 403].includes(error.response?.status) && getRefresh() === initial) clearSession()
      throw error
    })
    .finally(() => { refreshing = null })
  return refreshing
}

export async function ensureSession() {
  const token = decodeToken(getAccess())
  if (!token || token.exp <= Date.now() / 1000 + 60) return refreshSession()
  return getAccess()
}

api.interceptors.request.use(config => {
  const token = getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use(res => res, async error => {
  const original = error.config
  if (error.response?.status === 401 && original && !original._retry) {
    original._retry = true
    const sent = original.headers?.Authorization
    const current = getAccess()
    // A concurrent request may already have refreshed this access token.
    if (current && sent !== `Bearer ${current}`) {
      original.headers.Authorization = `Bearer ${current}`
      return api(original)
    }
    if (getRefresh()) {
      const token = await refreshSession()
      original.headers.Authorization = `Bearer ${token}`
      return api(original)
    }
    clearSession()
  }
  return Promise.reject(error)
})
export default api
