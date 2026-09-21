import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ListaPatologias from './ListaPatologias'

vi.mock('../../api', () => ({ api: { get: vi.fn(() => new Promise(() => {})) } }))

describe('ListaPatologias', () => {
  const mockPatologias = {
    'Neumonía': 0.85,
    'Consolidación': 0.42,
    'Derrame pleural': 0.15,
    'Atelectasia': 0.05,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renderiza la lista de patologías ordenada por probabilidad', () => {
    render(<ListaPatologias patologias={mockPatologias} />)

    expect(screen.getByText('Hallazgos detectados')).toBeInTheDocument()

    // Verificar orden descendente
    expect(screen.getByText('Neumonía').compareDocumentPosition(screen.getByText('Consolidación')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByText('Neumonía')).toBeInTheDocument()
    expect(screen.getByText('Consolidación')).toBeInTheDocument()
    expect(screen.getByText('Derrame pleural')).toBeInTheDocument()
  })

  it('no muestra patologías por debajo del umbral (5%)', () => {
    const patologiasConBajas = {
      ...mockPatologias,
      'Opacidad pulmonar': 0.03, // < 5%
    }
    render(<ListaPatologias patologias={patologiasConBajas} />)

    expect(screen.queryByText('Opacidad pulmonar')).not.toBeInTheDocument()
  })

  it('muestra estado vacío cuando no hay patologías', () => {
    render(<ListaPatologias patologias={{}} />)
    expect(screen.getByText('No se detectaron hallazgos')).toBeInTheDocument()
    expect(screen.getByText('El modelo no identificó patologías por encima del umbral de mención (5%).')).toBeInTheDocument()
  })

  it('muestra badges correctos según nivel de probabilidad', () => {
    render(<ListaPatologias patologias={mockPatologias} />)

    // Neumonía 85% -> ALTO (CRÍTICO)
    const neumoniaBadge = screen.getByText('Alto')
    expect(neumoniaBadge).toBeInTheDocument()

    // Consolidación 42% -> MODERADO
    const consolidacionBadge = screen.getByText('Moderado')
    expect(consolidacionBadge).toBeInTheDocument()

    // Los valores 15% y 5% quedan por debajo del umbral leve (20%).
    expect(screen.getAllByText('No significativo')).toHaveLength(2)
  })

  it('muestra porcentajes correctos', () => {
    render(<ListaPatologias patologias={mockPatologias} />)

    expect(screen.getByText('85%')).toBeInTheDocument()
    expect(screen.getByText('42%')).toBeInTheDocument()
    expect(screen.getByText('15%')).toBeInTheDocument()
    expect(screen.getByText('5%')).toBeInTheDocument()
  })

  it('muestra tooltip al hacer hover', () => {
    render(<ListaPatologias patologias={mockPatologias} />)

    const neumonia = screen.getByText('Neumonía')
    fireEvent.mouseEnter(neumonia)

    expect(screen.getByText('Pneumonia')).toBeInTheDocument()
    expect(screen.getByText('Infección bacteriana o viral del parénquima pulmonar con exudado alveolar')).toBeInTheDocument()
  })
})
