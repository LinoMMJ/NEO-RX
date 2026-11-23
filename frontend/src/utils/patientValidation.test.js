import { describe, expect, it } from 'vitest'
import { patientBirthDateBounds, validatePatient } from './patientValidation'

const today = new Date(2026, 10, 20)
const valid = {
  nombres: 'María-José', apellidos: "O’Connor Pérez", ci: '1234567 LP',
  fecha_nacimiento: '1990-04-15', genero: 'F', telefono: '+591 71234567',
}

describe('validación de pacientes', () => {
  it('acepta nombres internacionales e información válida', () => {
    expect(validatePatient(valid, today)).toEqual({})
  })

  it('acepta exactamente 100 años y rechaza más de 100', () => {
    expect(validatePatient({ ...valid, fecha_nacimiento: '1926-11-20' }, today).fecha_nacimiento).toBeUndefined()
    expect(validatePatient({ ...valid, fecha_nacimiento: '1925-11-20' }, today).fecha_nacimiento).toMatch(/más de 100/)
  })

  it('rechaza fechas futuras y campos con formato inválido', () => {
    const errors = validatePatient({
      ...valid, nombres: '123', ci: 'CI/123', telefono: 'ABC', fecha_nacimiento: '2026-11-21',
    }, today)
    expect(errors).toMatchObject({
      nombres: expect.any(String), ci: expect.any(String), telefono: expect.any(String),
      fecha_nacimiento: expect.any(String),
    })
  })

  it('calcula límites locales sin desplazamiento UTC', () => {
    expect(patientBirthDateBounds(today)).toEqual({ min: '1926-11-20', max: '2026-11-20' })
  })
})
