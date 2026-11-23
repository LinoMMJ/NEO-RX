import { test, expect } from '@playwright/test'
import { attachScreenshot, loginByUi } from './helpers.js'

test('CRUD visible de paciente y trazabilidad en auditoría', async ({ page }, testInfo) => {
  // El contrato del paciente admite CI de hasta 20 caracteres.
  const marker = `PW${Date.now().toString().slice(-10)}`
  await loginByUi(page, 'medico')
  await page.goto('/pacientes')
  await page.getByRole('button', { name: 'Nuevo paciente' }).click()
  await page.getByLabel('Nombres *').fill('Prueba')
  await page.getByLabel('Apellidos *').fill('Playwright Funcional')
  await page.getByLabel('CI *').fill(marker)
  await page.getByLabel('Fecha de nacimiento *').fill('1988-05-17')
  await page.getByLabel('Teléfono').fill('70000001')
  await page.getByRole('button', { name: 'Registrar paciente' }).click()
  await expect(page.getByText('Paciente registrado.')).toBeVisible()

  await page.getByLabel('Nombre o CI').fill(marker)
  await expect(page.getByRole('cell', { name: marker })).toBeVisible()
  await attachScreenshot(page, testInfo, '03-paciente-creado-y-localizado')

  await page.getByRole('button', { name: 'Editar a Prueba' }).click()
  await page.getByLabel('Teléfono').fill('70000002')
  await page.getByRole('button', { name: 'Actualizar paciente' }).click()
  await expect(page.getByText('Paciente actualizado.')).toBeVisible()
  await expect(page.getByRole('cell', { name: '70000002' })).toBeVisible()

  await page.goto('/actividad?action=create&resource_type=paciente')
  await expect(page.getByRole('heading', { name: 'Historial de movimientos' })).toBeVisible()
  await expect(page.getByRole('cell', { name: /Creación|Actualización/ }).first()).toBeVisible()
  await attachScreenshot(page, testInfo, '04-auditoria-del-paciente')
})
