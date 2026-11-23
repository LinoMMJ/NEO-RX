import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import PasswordResetFlow from './PasswordResetFlow'
import { requestPasswordReset, verifyPasswordReset, confirmPasswordReset } from '../../api/auth'

vi.mock('../../api/auth', () => ({
  requestPasswordReset: vi.fn(),
  verifyPasswordReset: vi.fn(),
  confirmPasswordReset: vi.fn(),
}))
vi.mock('../../api/session', () => ({ clearSession: vi.fn() }))

beforeEach(() => {
  requestPasswordReset.mockResolvedValue({ data: { message: 'Código enviado.' } })
  verifyPasswordReset.mockResolvedValue({ data: { reset_proof: 'proof-token', message: 'Código verificado.' } })
  confirmPasswordReset.mockResolvedValue({ data: { message: 'Contraseña actualizada.' } })
})

it('completa correo, código de seis dígitos y renovación antes de volver al login', async () => {
  const done = vi.fn()
  render(<PasswordResetFlow onDone={done} />)

  fireEvent.change(screen.getByLabelText('Correo electrónico registrado'), { target: { value: ' usuario@gmail.com ' } })
  fireEvent.click(screen.getByRole('button', { name: 'Enviar código' }))

  expect(await screen.findByText(/Vence en 15 minutos/)).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Código de seis dígitos'), { target: { value: '123456' } })
  fireEvent.click(screen.getByRole('button', { name: 'Verificar código' }))

  expect(await screen.findByRole('heading', { name: 'Nueva contraseña' })).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Nueva contraseña'), { target: { value: 'Strong-password-927!' } })
  fireEvent.change(screen.getByLabelText('Confirmar contraseña'), { target: { value: 'Strong-password-927!' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }))

  await waitFor(() => expect(done).toHaveBeenCalledTimes(1))
  expect(requestPasswordReset).toHaveBeenCalledWith('usuario@gmail.com')
  expect(verifyPasswordReset).toHaveBeenCalledWith('usuario@gmail.com', '123456')
  expect(confirmPasswordReset).toHaveBeenCalledWith('usuario@gmail.com', 'proof-token', 'Strong-password-927!')
})
