export function calcularEdad(fecha) {
  if (!fecha) return null
  const n = new Date(`${fecha}T00:00:00`)
  if (isNaN(n)) return null
  const hoy = new Date()
  let edad = hoy.getFullYear() - n.getFullYear()
  const m = hoy.getMonth() - n.getMonth()
  if (m < 0 || (m === 0 && hoy.getDate() < n.getDate())) edad--
  return edad
}
