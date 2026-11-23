import { test, expect } from '@playwright/test'
import { apiLogin, attachScreenshot, authenticatedPage } from './helpers.js'

test.describe('Métricas, seguridad y auditoría administrativa', () => {
  test('el tablero administrativo muestra métricas reales', async ({ page, request }, testInfo) => {
    await authenticatedPage(page, request, 'administrador')
    await page.getByRole('button', { name: 'Administración' }).click()
    await expect(page.getByText('Control de usuarios')).toBeVisible()
    await expect(page.getByText('Movimientos del período')).toBeVisible()
    await attachScreenshot(page, testInfo, '05-tablero-metricas-administrativas')

    await page.getByRole('link', { name: 'Consultar historial de movimientos' }).click()
    await expect(page.getByRole('heading', { name: 'Historial de movimientos' })).toBeVisible()
    await expect(page.getByRole('table')).toBeVisible()
    await attachScreenshot(page, testInfo, '06-historial-global-auditoria')
  })

  test('API protege recursos y entrega métricas estructuradas', async ({ request }) => {
    const anonymous = await request.get('/api/metrics/operacionales/')
    expect(anonymous.status()).toBe(401)

    const medicoHeaders = await apiLogin(request, 'medico')
    const forbidden = await request.get('/api/admin/users/', { headers: medicoHeaders })
    expect(forbidden.status()).toBe(403)

    const metrics = await request.get('/api/metrics/operacionales/', { headers: medicoHeaders })
    expect(metrics.ok()).toBeTruthy()
    const payload = await metrics.json()
    expect(payload).toEqual(expect.objectContaining({
      metricas_cnn: expect.any(Object),
      latencia_diagnostico: expect.any(Object),
    }))
  })

  test('cabeceras defensivas y almacenamiento de sesión temporal', async ({ page, request }) => {
    const response = await request.get('/health/')
    expect(response.ok()).toBeTruthy()
    // Django y Nginx pueden aportar la misma cabecera; debe estar presente
    // aunque el proxy la combine como una lista separada por comas.
    expect(response.headers()['x-content-type-options']).toContain('nosniff')
    expect(response.headers()['x-frame-options']).toContain('DENY')

    await authenticatedPage(page, request, 'medico')
    const storage = await page.evaluate(() => ({
      sessionAccess: Boolean(sessionStorage.getItem('access_token')),
      sessionRefresh: Boolean(sessionStorage.getItem('refresh_token')),
      localAccess: localStorage.getItem('access_token'),
      localRefresh: localStorage.getItem('refresh_token'),
    }))
    expect(storage.sessionAccess).toBeTruthy()
    expect(storage.sessionRefresh).toBeTruthy()
    expect(storage.localAccess).toBeNull()
    expect(storage.localRefresh).toBeNull()
  })
})
