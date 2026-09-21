export const UMBRALES_GENERALES = { alto: 0.65, moderado: 0.40, leve: 0.20 }

export const UMBRALES_PATOLOGIA = {
  'Neumonía': { alto: 0.60, moderado: 0.35, leve: 0.15 },
  'Neumotórax': { alto: 0.70, moderado: 0.45, leve: 0.20 },
  'Consolidación': { alto: 0.60, moderado: 0.35, leve: 0.15 },
  'Derrame pleural': { alto: 0.65, moderado: 0.40, leve: 0.20 },
}

export const NIVEL_LABELS = {
  alto: 'Alto',
  moderado: 'Moderado',
  leve: 'Leve',
  marginal: 'No significativo',
}

export const NIVEL_COLORS = {
  alto: 'danger',
  moderado: 'orange',
  leve: 'warning',
  marginal: 'slate',
}

export function obtener_umbrales(patologia) {
  return UMBRALES_PATOLOGIA[patologia] ?? UMBRALES_GENERALES
}

export function clasificar_probabilidad(patologia, probabilidad) {
  const umbrales = obtener_umbrales(patologia)
  let etiqueta = 'marginal'
  let umbral_usado = 0
  if (probabilidad >= umbrales.alto) {
    etiqueta = 'alto'; umbral_usado = umbrales.alto
  } else if (probabilidad >= umbrales.moderado) {
    etiqueta = 'moderado'; umbral_usado = umbrales.moderado
  } else if (probabilidad >= umbrales.leve) {
    etiqueta = 'leve'; umbral_usado = umbrales.leve
  }
  return {
    etiqueta,
    color: NIVEL_COLORS[etiqueta],
    umbral_usado,
    descripcion: etiqueta === 'alto'
      ? 'Hallazgo de alta probabilidad; requiere correlación clínica urgente.'
      : 'Interpretar junto con la evaluación clínica.',
  }
}

export function clasificar_todas(patologias) {
  return Object.fromEntries(Object.entries(patologias).map(([nombre, probabilidad]) => {
    const clasificacion = clasificar_probabilidad(nombre, probabilidad)
    return [nombre, { nivel: clasificacion.etiqueta, probabilidad, ...clasificacion }]
  }))
}
