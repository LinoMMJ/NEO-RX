import { useState, useCallback, useEffect } from 'react'
import { login as apiLogin, logout as apiLogout, getTokenPayload } from '../api/auth'
import { ensureSession } from '../api/axios'
import { hasSession, clearSession } from '../api/session'
import { AuthContext } from './useAuth'
export function AuthProvider({ children }) {
  const [identity, setIdentity] = useState(null)
  const [ready, setReady] = useState(false)
  useEffect(() => {
    let active = true
    const sync = () => { if (active) setIdentity(hasSession() ? getTokenPayload() : null) }
    const renew = async () => {
      if (!hasSession()) { clearSession(); return }
      try { await ensureSession() } catch { /* Network failures don't destroy a valid refresh token. */ }
      sync()
    }
    window.addEventListener('auth-changed', sync)
    window.addEventListener('storage', sync)
    const visible = () => { if (document.visibilityState === 'visible') renew() }
    document.addEventListener('visibilitychange', visible)
    renew().finally(() => { if (active) setReady(true) })
    const timer = setInterval(renew, 30000)
    return () => { active = false; clearInterval(timer); window.removeEventListener('auth-changed', sync); window.removeEventListener('storage', sync); document.removeEventListener('visibilitychange', visible) }
  }, [])
  const login = useCallback(async (username, password, remember = false) => { await apiLogin(username, password, remember) }, [])
  const logout = useCallback(() => { apiLogout().catch(() => {}) }, [])
  return <AuthContext.Provider value={{ user: identity?.username || null, rol: identity?.rol || null, isAuth: !!identity, ready, login, logout }}>{children}</AuthContext.Provider>
}
