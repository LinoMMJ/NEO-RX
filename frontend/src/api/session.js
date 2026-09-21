// Central token storage: closing the tab clears ordinary sessions.
export function decodeToken(token) {
  if (!token) return null
  try {
    let encoded = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    encoded += '='.repeat((4 - encoded.length % 4) % 4)
    return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(encoded), c => c.charCodeAt(0))))
  } catch { return null }
}
export const getAccess = () => sessionStorage.getItem('access_token') || localStorage.getItem('access_token')
export const getRefresh = () => sessionStorage.getItem('refresh_token') || localStorage.getItem('refresh_token')
export const isRemembered = () => !sessionStorage.getItem('refresh_token') && !!localStorage.getItem('refresh_token')
export const notifySession = () => window.dispatchEvent(new Event('auth-changed'))
export function clearSession() {
  for (const storage of [sessionStorage, localStorage]) {
    storage.removeItem('access_token'); storage.removeItem('refresh_token')
  }
  notifySession()
}
export function saveSession(tokens, remember = isRemembered()) {
  const storage = remember ? localStorage : sessionStorage
  const other = remember ? sessionStorage : localStorage
  for (const key of ['access_token', 'refresh_token']) other.removeItem(key)
  storage.setItem('access_token', tokens.access)
  storage.setItem('refresh_token', tokens.refresh)
  notifySession()
}
export function hasSession() {
  const token = decodeToken(getRefresh())
  return !!token && token.exp > Date.now() / 1000
}
