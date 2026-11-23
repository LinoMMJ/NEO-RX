import { expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '../..')

function readDockerEnv() {
  const file = path.join(root, '.env.docker')
  const values = {}
  for (const raw of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = raw.trim()
    if (!line || line.startsWith('#') || !line.includes('=')) continue
    const index = line.indexOf('=')
    values[line.slice(0, index).trim()] = line.slice(index + 1).trim()
  }
  return values
}

const env = readDockerEnv()
export const credentials = {
  medico: { username: 'medico', password: env.NEORX_MEDICO_PASSWORD },
  administrador: { username: 'admin', password: env.NEORX_ADMIN_PASSWORD },
  recepcionista: { username: 'recepcionista', password: env.NEORX_RECEPCIONISTA_PASSWORD },
}

// Una suite completa no debe sobrepasar deliberadamente el límite productivo
// de 5 inicios de sesión por minuto. Los JWT se reutilizan solo en memoria
// durante el proceso de Playwright y desaparecen al terminarlo.
const tokenCache = new Map()

for (const [role, value] of Object.entries(credentials)) {
  if (!value.password) throw new Error(`Falta la contraseña Docker para ${role}`)
}

export const demoImage = path.join(
  root,
  'muestras_presentacion_preentrenado',
  '01_derrame_pleural__00008777_001.png',
)

export async function loginByUi(page, role = 'medico') {
  const account = credentials[role]
  const cached = tokenCache.get(role)
  if (cached) {
    await installSession(page, cached)
    return
  }
  await page.goto('/login')
  await page.getByLabel('Usuario o correo electrónico').fill(account.username)
  await page.getByLabel('Contraseña', { exact: true }).fill(account.password)
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole('heading', { name: 'Tablero' })).toBeVisible()
  const tokens = await page.evaluate(() => ({
    access: sessionStorage.getItem('access_token'),
    refresh: sessionStorage.getItem('refresh_token'),
  }))
  if (!tokens.access || !tokens.refresh) throw new Error(`El login ${role} no almacenó JWT de sesión`)
  tokenCache.set(role, tokens)
}

export async function apiLogin(request, role = 'medico') {
  const tokens = await obtainTokens(request, role)
  return { Authorization: `Bearer ${tokens.access}` }
}

export async function authenticatedPage(page, request, role = 'medico') {
  const tokens = await obtainTokens(request, role)
  await installSession(page, tokens)
}

async function obtainTokens(request, role) {
  if (tokenCache.has(role)) return tokenCache.get(role)
  const response = await request.post('/api/token/', { data: credentials[role] })
  expect(response.ok(), `Login API ${role}: HTTP ${response.status()}`).toBeTruthy()
  const tokens = await response.json()
  tokenCache.set(role, tokens)
  return tokens
}

async function installSession(page, tokens) {
  await page.goto('/login')
  await page.evaluate(({ access, refresh }) => {
    sessionStorage.setItem('access_token', access)
    sessionStorage.setItem('refresh_token', refresh)
    window.dispatchEvent(new Event('auth-changed'))
  }, tokens)
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Tablero' })).toBeVisible()
}

export async function attachScreenshot(page, testInfo, name, fullPage = true) {
  const body = await page.screenshot({ fullPage, animations: 'disabled' })
  await testInfo.attach(name, { body, contentType: 'image/png' })
}

export function uniqueId(prefix = 'PW') {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 10000)}`
}
