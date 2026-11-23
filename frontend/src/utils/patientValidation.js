const NAME_PATTERN = /^[\p{L}\p{M} .''’-]+$/u
const IDENTIFIER_PATTERN = /^[\p{L}\p{N} ._-]+$/u
const PHONE_PATTERN = /^[+()\d -]+$/

export function localISODate(value = new Date()) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function patientBirthDateBounds(today = new Date()) {
  const oldest = new Date(today.getFullYear() - 100, today.getMonth(), today.getDate())
  return { min: localISODate(oldest), max: localISODate(today) }
}

function ageAt(dateValue, today = new Date()) {
  const [year, month, day] = String(dateValue).split('-').map(Number)
  if (!year || !month || !day) return null
  let age = today.getFullYear() - year
  if (today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day)) age--
  return age
}

export function validatePatient(form, today = new Date()) {
  const errors = {}
  const names = form.nombres?.trim() || ''
  const surnames = form.apellidos?.trim() || ''
  const identifier = form.ci?.trim() || ''
  const phone = form.telefono?.trim() || ''

  if (!names) errors.nombres = 'Los nombres son obligatorios.'
  else if (names.length > 100) errors.nombres = 'Máximo 100 caracteres.'
  else if (!NAME_PATTERN.test(names)) errors.nombres = 'Use letras, espacios, apóstrofes, puntos o guiones.'

  if (!surnames) errors.apellidos = 'Los apellidos son obligatorios.'
  else if (surnames.length > 100) errors.apellidos = 'Máximo 100 caracteres.'
  else if (!NAME_PATTERN.test(surnames)) errors.apellidos = 'Use letras, espacios, apóstrofes, puntos o guiones.'

  if (!identifier) errors.ci = 'El identificador es obligatorio.'
  else if (identifier.length > 20) errors.ci = 'Máximo 20 caracteres.'
  else if (!IDENTIFIER_PATTERN.test(identifier)) errors.ci = 'Use letras, números, espacios, puntos o guiones.'

  if (!form.fecha_nacimiento) errors.fecha_nacimiento = 'La fecha de nacimiento es obligatoria.'
  else {
    const age = ageAt(form.fecha_nacimiento, today)
    if (age === null) errors.fecha_nacimiento = 'Ingrese una fecha válida.'
    else if (age < 0) errors.fecha_nacimiento = 'La fecha de nacimiento no puede ser futura.'
    else if (age > 100) errors.fecha_nacimiento = 'No se puede registrar una persona con más de 100 años.'
  }

  if (!['M', 'F', 'Otro'].includes(form.genero)) errors.genero = 'Seleccione un género válido.'

  if (phone) {
    const digits = phone.replace(/\D/g, '').length
    if (phone.length > 20) errors.telefono = 'Máximo 20 caracteres.'
    else if (!PHONE_PATTERN.test(phone) || (phone.includes('+') && (!phone.startsWith('+') || phone.split('+').length > 2))) errors.telefono = 'Use números, espacios, +, guiones o paréntesis.'
    else if (digits < 7 || digits > 15) errors.telefono = 'Debe contener entre 7 y 15 dígitos.'
  }
  return errors
}
