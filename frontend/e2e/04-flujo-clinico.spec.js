import { test, expect } from '@playwright/test'
import { apiLogin, attachScreenshot, authenticatedPage, demoImage } from './helpers.js'

test('flujo clínico: carga, CNN, resultado, Grad-CAM e informe', async ({ page, request }, testInfo) => {
  test.setTimeout(300_000)
  const headers = await apiLogin(request, 'medico')
  const marker = `CL${Date.now().toString().slice(-10)}`
  const patientResponse = await request.post('/api/pacientes/', {
    headers,
    data: {
      nombres: 'Caso', apellidos: 'Playwright Clinico', ci: marker,
      fecha_nacimiento: '1975-03-12', genero: 'Otro', telefono: '',
    },
  })
  expect(patientResponse.status()).toBe(201)
  const patient = await patientResponse.json()

  await authenticatedPage(page, request, 'medico')
  await page.goto(`/escaneo?paciente=${patient.id}`)
  await expect(page.getByText('Caso Playwright Clinico')).toBeVisible()
  await page.locator('input[type="file"]').setInputFiles(demoImage)
  await expect(page.getByAltText('Vista previa de la radiografía seleccionada')).toBeVisible()
  await page.getByLabel('Observaciones clínicas').fill('Caso automatizado para evidencia funcional Playwright.')
  await page.getByRole('button', { name: 'Validar y continuar' }).click()

  const prioritizedFindings = page.getByRole('list', { name: 'Hallazgos prioritarios detectados' })
  await expect(prioritizedFindings).toBeVisible({ timeout: 180_000 })
  await expect(prioritizedFindings).toContainText('Derrame pleural')
  await expect(prioritizedFindings).toContainText(/Puntuación:\s*\d+(?:\.\d+)?\/100/)
  await expect(page.getByText(/Nitidez OK/)).toBeVisible()
  await attachScreenshot(page, testInfo, '07-resultado-cnn-derrame')

  const generateHeatmap = page.getByRole('button', { name: 'Generar mapa de calor del resultado principal' })
  if (await generateHeatmap.isVisible()) await generateHeatmap.click()
  const overlay = page.getByRole('button', { name: 'Superposición CNN' })
  await expect(overlay).toBeEnabled({ timeout: 120_000 })
  await overlay.click()
  await expect(page.getByText('Alta activación')).toBeVisible()
  await attachScreenshot(page, testInfo, '08-gradcam-regional')

  const openReport = page.getByRole('button', { name: 'Abrir informe' })
  await expect(openReport).toBeVisible()
  await openReport.click()
  await expect(page).toHaveURL(/\/informes\/\d+$/)
  await expect(page.getByText('Descargar preinforme (PDF)')).toBeVisible()
  await attachScreenshot(page, testInfo, '09-editor-preinforme')
})
