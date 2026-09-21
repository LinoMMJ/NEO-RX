import test from 'node:test'
import assert from 'node:assert/strict'
import axios, { AxiosError } from 'axios'
const memory = () => { const values = new Map(); return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, String(value)), removeItem: key => values.delete(key) } }
globalThis.localStorage = memory(); globalThis.sessionStorage = memory()
globalThis.window = new EventTarget()
Object.defineProperty(globalThis, 'navigator', { value: {}, configurable: true })
let adapter
axios.defaults.adapter = config => adapter(config)
const session = await import('../src/api/session.js')
const { default: api, refreshSession, ensureSession } = await import('../src/api/axios.js')
const auth = await import('../src/api/auth.js')
const token = (extra = {}) => `unit.${Buffer.from(JSON.stringify({ exp: Date.now() / 1000 + 3600, username: 'Synthetic', ...extra })).toString('base64url')}.signature`
const response = (config, data) => ({ status: 200, statusText: 'OK', headers: {}, config, data })
const unauthorized = config => new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, null, { status: 401, data: {} })
const reset = () => { session.clearSession(); navigator.locks = undefined }

test('ordinary login uses tab storage; remembered login persists; logout clears both', async () => {
  reset(); adapter = async config => response(config, { access: token(), refresh: token() })
  await auth.login('Synthetic', 'test', false)
  assert.ok(sessionStorage.getItem('refresh_token')); assert.equal(localStorage.getItem('refresh_token'), null)
  await auth.login('Synthetic', 'test', true)
  assert.ok(localStorage.getItem('refresh_token')); assert.equal(sessionStorage.getItem('refresh_token'), null)
  await auth.logout(); assert.equal(session.getRefresh(), null); assert.equal(session.getAccess(), null)
})

test('parallel 401 requests rotate only once and store the new refresh token', async () => {
  reset(); const old = token({ generation: 1 }), next = token({ generation: 2 }), rotated = token({ generation: 3 })
  session.saveSession({ access: old, refresh: token({ generation: 0 }) }, true)
  let count = 0
  adapter = async config => {
    if (config.url.endsWith('/token/refresh/')) { count++; await new Promise(resolve => setTimeout(resolve, 15)); return response(config, { access: next, refresh: rotated }) }
    if (config.headers.Authorization !== `Bearer ${next}`) throw unauthorized(config)
    return response(config, { ok: true })
  }
  const results = await Promise.all([api.get('/patients/'), api.get('/patients/')])
  assert.equal(count, 1); assert.ok(results.every(r => r.data.ok))
  assert.equal(session.getRefresh(), rotated); assert.equal(localStorage.getItem('access_token'), next)
})

test('proactive renewal refreshes an expiring access token', async () => {
  reset(); session.saveSession({ access: token({ exp: Date.now() / 1000 + 5 }), refresh: token() }, false)
  let count = 0
  adapter = async config => { count++; return response(config, { access: token(), refresh: token({ renewed: true }) }) }
  await ensureSession(); assert.equal(count, 1)
})

test('temporary network failure preserves the refresh token; revoked token clears it', async () => {
  reset(); const current = token(); session.saveSession({ access: token(), refresh: current }, false)
  adapter = async () => { throw new Error('Network unavailable') }
  await assert.rejects(refreshSession()); assert.equal(session.getRefresh(), current)
  adapter = async config => { throw unauthorized(config) }
  await assert.rejects(refreshSession()); assert.equal(session.getRefresh(), null)
})

test('refresh finishing after logout cannot resurrect the session', async () => {
  reset(); session.saveSession({ access: token(), refresh: token() }, true)
  let release
  adapter = config => new Promise(resolve => { release = () => resolve(response(config, { access: token(), refresh: token() })) })
  const pending = refreshSession(); session.clearSession(); release()
  await assert.rejects(pending); assert.equal(session.getRefresh(), null)
})

test('a tab waiting for a refresh lock uses the token another tab already rotated', async () => {
  reset(); session.saveSession({ access: token(), refresh: token() }, true)
  let release; let calls = 0
  navigator.locks = { request: async (name, perform) => { await new Promise(resolve => { release = resolve }); return perform() } }
  adapter = async () => { calls++; throw new Error('Should not contact server') }
  const pending = refreshSession()
  const newer = token({ generation: 9 }); session.saveSession({ access: newer, refresh: token({ generation: 10 }) }, true)
  release(); assert.equal(await pending, newer); assert.equal(calls, 0)
})

test('JWT display decoder handles Unicode and invalid tokens without crashing', () => {
  reset(); assert.equal(session.decodeToken(token({ username: 'Médico' })).username, 'Médico')
  assert.equal(session.decodeToken('invalid'), null)
  session.saveSession({ access: token(), refresh: token({ exp: 1 }) }, false)
  assert.equal(session.hasSession(), false)
})
