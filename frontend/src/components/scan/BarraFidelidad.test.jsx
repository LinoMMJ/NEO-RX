import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import BarraFidelidad from './BarraFidelidad'

describe('BarraFidelidad', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('no renderiza nada si probabilidad es null', () => {
    render(<BarraFidelidad patologiaPrincipal="Neumonía" probabilidad={null} />)
    expect(screen.queryByText('Confianza diagnóstica')).not.toBeInTheDocument()
  })

  it('renderiza barra con porcentaje correcto', () => {
    render(<BarraFidelidad patologiaPrincipal="Neumonía" probabilidad={0.85} />)

    expect(screen.getByText('Confianza diagnóstica')).toBeInTheDocument()
    expect(screen.getByText('85%')).toBeInTheDocument()
    expect(screen.getByText('Neumonía')).toBeInTheDocument()
  })

  it('muestra nivel ELEVADO para probabilidad >= 70%', () => {
    render(<BarraFidelidad patologiaPrincipal="Neumonía" probabilidad={0.85} />)
    expect(screen.getByText('ELEVADO')).toBeInTheDocument()
  })

  it('muestra nivel MODERADO para probabilidad 50-70%', () => {
    render(<BarraFidelidad patologiaPrincipal="Consolidación" probabilidad={0.60} />)
    expect(screen.getByText('MODERADO')).toBeInTheDocument()
  })

  it('muestra nivel LEVE para probabilidad 30-50%', () => {
    render(<BarraFidelidad patologiaPrincipal="Derrame pleural" probabilidad={0.40} />)
    expect(screen.getByText('LEVE')).toBeInTheDocument()
  })

  it('muestra nivel MARGINAL para probabilidad < 30%', () => {
    render(<BarraFidelidad patologiaPrincipal="Atelectasia" probabilidad={0.20} />)
    expect(screen.getByText('MARGINAL')).toBeInTheDocument()
  })

  it('muestra tiempo de inferencia si se proporciona', () => {
    render(<BarraFidelidad patologiaPrincipal="Neumonía" probabilidad={0.85} tiempoInferencia={0.45} />)
    expect(screen.getByText('Inferencia: 0.45s')).toBeInTheDocument()
  })

  it('muestra umbrales en la barra', () => {
    render(<BarraFidelidad patologiaPrincipal="Neumonía" probabilidad={0.85} />)
    expect(screen.getByText('umbral 30%')).toBeInTheDocument()
    expect(screen.getByText('umbral 50%')).toBeInTheDocument()
  })
})