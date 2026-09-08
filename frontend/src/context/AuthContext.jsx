import { createContext, useContext, useState, useCallback } from 'react'
import { login as apiLogin, logout as apiLogout, getTokenPayload } from '../api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const payload = getTokenPayload()
  const [user, setUser] = useState(payload?.username || null)
  const [rol, setRol] = useState(payload?.rol || null)

  const login = useCallback(async (username, password) => {
    await apiLogin(username, password)
    const p = getTokenPayload()
    setUser(p?.username || username)
    setRol(p?.rol || null)
  }, [])

  const logout = useCallback(() => {
    apiLogout()
    setUser(null)
    setRol(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, rol, login, logout, isAuth: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
