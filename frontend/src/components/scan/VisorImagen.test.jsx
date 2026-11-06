import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import VisorImagen from './VisorImagen'

vi.mock('../../hooks/usePrivateImage', () => ({ default: () => null }))

describe('Objetivos de Grad-CAM', () => {
  it('solicita la salida de categoría indicada por backend', () => {
    const change = vi.fn()
    render(<VisorImagen objetivosGradcam={[{ etiqueta: 'Orientación tumoral', etiqueta_en: 'CategoryTumoral' }]}
      onPatologiaChange={change} />)
    fireEvent.click(screen.getByRole('button', { name: 'Generar mapa de calor del resultado principal' }))
    expect(change).toHaveBeenCalledWith('CategoryTumoral')
  })

  it('una abstención explícita no recupera un objetivo de puntuaciones antiguas', () => {
    render(<VisorImagen objetivosGradcam={[]} patologias={{ 'Derrame pleural': 0.99 }} />)
    expect(screen.queryByRole('button', { name: /Generar mapa de calor/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Derrame pleural' })).not.toBeInTheDocument()
  })
})
