import axios from 'axios'
import { getAccess, getRefresh, decodeToken, saveSession, clearSession } from './session.js'
const BASE = import.meta.env?.VITE_API_URL || 'http://localhost:8000/api'
export const login = async (username, password, remember = false) => {
  const { data } = await axios.post(`${BASE}/token/`, { username, password, remember_me: remember })
  saveSession(data, remember)
  return data
}
export const logout = async () => {
  const access = getAccess(), refresh = getRefresh()
  // Capture tokens, then immediately clear UI even if the network is unavailable.
  clearSession()
  if (access && refresh) await axios.post(`${BASE}/token/logout/`, { refresh }, {
    headers: { Authorization: `Bearer ${access}` },
  })
}
export const getTokenPayload = () => decodeToken(getAccess())
export const requestPasswordReset = email => axios.post(`${BASE}/password/reset/`, { email })
export const verifyPasswordReset = (email, code) => axios.post(`${BASE}/password/reset/verify/`, { email, code })
export const confirmPasswordReset = (email, reset_proof, new_password) => axios.post(`${BASE}/password/reset/confirm/`, { email, reset_proof, new_password })
