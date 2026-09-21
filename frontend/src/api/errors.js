export function fieldErrors(error) {
  return error.response?.data?.errors || {}
}
export function errorMessage(error, fallback = 'No se pudo guardar. Inténtalo nuevamente.') {
  const data = error.response?.data
  const errors = data?.errors
  if (errors && typeof errors === 'object') return Object.entries(errors).map(([field, value]) => `${field}: ${Array.isArray(value) ? value.join(' ') : value}`).join(' · ')
  return (Array.isArray(data?.error) ? data.error.join(' ') : data?.error) || (data?.detail !== 'Error en la solicitud' ? data?.detail : null) || fallback
}
