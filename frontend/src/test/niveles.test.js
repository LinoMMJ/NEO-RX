import { describe, it, expect } from 'vitest'
import {
  obtener_umbrales,
  clasificar_probabilidad,
  clasificar_todas,
  NIVEL_LABELS,
  NIVEL_COLORS,
} from '../utils/niveles'

describe('Niveles clínicos del fallback frontend', () => {
  it('usa umbrales específicos y generales', () => {
    expect(obtener_umbrales('Neumonía')).toEqual({ alto: 0.60, moderado: 0.35, leve: 0.15 })
    expect(obtener_umbrales('Patología desconocida')).toEqual({ alto: 0.65, moderado: 0.40, leve: 0.20 })
  })

  it('clasifica alto, moderado, leve y marginal', () => {
    expect(clasificar_probabilidad('Neumonía', 0.80).etiqueta).toBe('alto')
    expect(clasificar_probabilidad('Neumonía', 0.50).etiqueta).toBe('moderado')
    expect(clasificar_probabilidad('Neumonía', 0.30).etiqueta).toBe('leve')
    expect(clasificar_probabilidad('Neumonía', 0.10).etiqueta).toBe('marginal')
  })

  it('conserva probabilidad y descripción al clasificar un conjunto', () => {
    const resultado = clasificar_todas({ Neumonía: 0.75 })
    expect(resultado.Neumonía.probabilidad).toBe(0.75)
    expect(resultado.Neumonía.descripcion).toContain('correlación clínica urgente')
  })

  it('expone etiquetas y colores coherentes', () => {
    expect(NIVEL_LABELS.alto).toBe('Alto')
    expect(NIVEL_LABELS.marginal).toBe('No significativo')
    expect(NIVEL_COLORS.moderado).toBe('orange')
    expect(NIVEL_COLORS.leve).toBe('warning')
  })
})
