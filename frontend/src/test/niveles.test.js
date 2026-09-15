import { describe, it, expect } from 'vitest'
import {
  obtener_umbrales,
  clasificar_probabilidad,
  clasificar_todas,
  NIVEL_LABELS,
  NIVEL_COLORS,
} from '../../backend/diagnostico/niveles'

describe('Niveles Clínicos', () => {
  describe('obtener_umbrales', () => {
    it('retorna umbrales específicos para Neumonía', () => {
      const u = obtener_umbrales('Neumonía')
      expect(u.alto).toBe(0.60)
      expect(u.moderado).toBe(0.35)
      expect(u.leve).toBe(0.15)
    })

    it('retorna umbrales específicos para Neumotórax', () => {
      const u = obtener_umbrales('Neumotórax')
      expect(u.alto).toBe(0.70)
      expect(u.moderado).toBe(0.45)
      expect(u.leve).toBe(0.20)
    })

    it('retorna umbrales generales para patología desconocida', () => {
      const u = obtener_umbrales('PatologiaInexistente')
      expect(u.alto).toBe(0.65)
      expect(u.moderado).toBe(0.40)
      expect(u.leve).toBe(0.20)
    })
  })

  describe('clasificar_probabilidad', () => {
    it('clasifica ALTO para probabilidad >= umbral alto', () => {
      const nivel = clasificar_probabilidad('Neumonía', 0.80)
      expect(nivel.etiqueta).toBe('alto')
      expect(nivel.color).toBe('danger')
      expect(nivel.umbral_usado).toBe(0.60)
    })

    it('clasifica MODERADO para probabilidad entre moderado y alto', () => {
      const nivel = clasificar_probabilidad('Neumonía', 0.50)
      expect(nivel.etiqueta).toBe('moderado')
      expect(nivel.color).toBe('orange')
    })

    it('clasifica LEVE para probabilidad entre leve y moderado', () => {
      const nivel = clasificar_probabilidad('Neumonía', 0.30)
      expect(nivel.etiqueta).toBe('leve')
      expect(nivel.color).toBe('warning')
    })

    it('clasifica MARGINAL para probabilidad < umbral leve', () => {
      const nivel = clasificar_probabilidad('Neumonía', 0.10)
      expect(nivel.etiqueta).toBe('marginal')
      expect(nivel.color).toBe('slate')
    })
  })

  describe('clasificar_todas', () => {
    it('clasifica múltiples patologías correctamente', () => {
      const patologias = {
        'Neumonía': 0.85,
        'Consolidación': 0.50,
        'Derrame pleural': 0.30,
        'Atelectasia': 0.10,
      }

      const resultado = clasificar_todas(patologias)

      expect(resultado['Neumonía'].nivel).toBe('alto')
      expect(resultado['Consolidación'].nivel).toBe('moderado')
      expect(resultado['Derrame pleural'].nivel).toBe('leve')
      expect(resultado['Atelectasia'].nivel).toBe('marginal')
    })

    it('incluye probabilidad original en resultado', () => {
      const resultado = clasificar_todas({ 'Neumonía': 0.75 })
      expect(resultado['Neumonía'].probabilidad).toBe(0.75)
    })

    it('incluye descripción en resultado', () => {
      const resultado = clasificar_todas({ 'Neumonía': 0.80 })
      expect(resultado['Neumonía'].descripcion).toContain('correlación clínica urgente')
    })
  })

  describe('Constantes', () => {
    it('tiene labels correctos', () => {
      expect(NIVEL_LABELS.alto).toBe('Alto')
      expect(NIVEL_LABELS.moderado).toBe('Moderado')
      expect(NIVEL_LABELS.leve).toBe('Leve')
      expect(NIVEL_LABELS.marginal).toBe('No significativo')
    })

    it('tiene colores correctos', () => {
      expect(NIVEL_COLORS.alto).toBe('danger')
      expect(NIVEL_COLORS.moderado).toBe('orange')
      expect(NIVEL_COLORS.leve).toBe('warning')
      expect(NIVEL_COLORS.marginal).toBe('slate')
    })
  })
})