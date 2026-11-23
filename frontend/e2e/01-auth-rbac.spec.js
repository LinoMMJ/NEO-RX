import { test, expect } from '@playwright/test'
import { attachScreenshot, loginByUi } from './helpers.js'

test.describe('Autenticación y control de acceso', () => {
  test('un visitante es redirigido al inicio de sesión', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible()
  })

  test('rechaza credenciales inválidas sin exponer detalles internos', async ({ page }, testInfo) => {
    await page.goto('/login')
    await page.getByLabel('Usuario o correo electrónico').fill('usuario-inexistente-playwright')
    await page.getByLabel('Contraseña', { exact: true }).fill('Clave-invalida-Playwright-01!')
    await page.getByRole('button', { name: 'Ingresar' }).click()
    await expect(page.getByText('Credenciales incorrectas. Verifica tu usuario o correo y contraseña.')).toBeVisible()
    await expect(page.locator('body')).not.toContainText(/traceback|django|exception/i)
    await attachScreenshot(page, testInfo, '01-login-rechazado-sin-detalles-internos')
  })

  for (const role of ['medico', 'recepcionista', 'administrador']) {
    test(`inicia sesión correctamente como ${role}`, async ({ page }, testInfo) => {
      await loginByUi(page, role)
      const roleLabel = role === 'administrador' ? 'Administrador' : role === 'medico' ? 'Médico radiólogo' : 'Recepcionista'
      await expect(page.getByText(roleLabel, { exact: true }).last()).toBeVisible()
      await attachScreenshot(page, testInfo, `02-tablero-${role}`)
    })
  }

  test('recepción no puede abrir gestión de usuarios', async ({ page }) => {
    await loginByUi(page, 'recepcionista')
    await page.goto('/admin/usuarios')
    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: 'Tablero' })).toBeVisible()
  })
})
