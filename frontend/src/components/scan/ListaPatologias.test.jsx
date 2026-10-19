import { render, screen, within } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ListaPatologias from './ListaPatologias'
import { partitionFindings } from '../../utils/modelFindings'

const scores = { 'Fibrosis pulmonar': 0.78, 'Nódulo pulmonar': 0.71, 'Enfisema': 0.61 }
const findings = Object.keys(scores).map((etiqueta, index) => ({ etiqueta, threshold_usado: [0.5, 0.8, 0.7][index] }))

describe('ListaPatologias', () => {
  it('destaca solo señales que superan su umbral y conserva el resto en detalle', () => {
    render(<ListaPatologias patologias={scores} hallazgos={findings} />)
    const candidates = screen.getByRole('list', { name: 'Señales sobre umbral' })
    expect(within(candidates).getByText('Fibrosis pulmonar')).toBeInTheDocument()
    expect(within(candidates).queryByText('Nódulo pulmonar')).not.toBeInTheDocument()
    expect(screen.getByText('Nódulo pulmonar')).not.toBeVisible()
    expect(screen.getByText('Ver otras puntuaciones (2)')).toBeInTheDocument()
    expect(screen.getByText('78.0/100')).toBeInTheDocument()
    expect(screen.queryByText('78.0%')).not.toBeInTheDocument()
  })
  it('no inventa un ganador cuando varias clases superan su umbral', () => {
    render(<ListaPatologias patologias={scores} hallazgos={findings.map((f) => ({...f, threshold_usado: 0.5}))} />)
    expect(screen.getByText('3 señales superan sus umbrales')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('no permite escoger un diagnóstico único')
  })
  it('no declara normalidad si ninguna clase supera su umbral', () => {
    render(<ListaPatologias patologias={scores} hallazgos={findings.map((f) => ({...f, threshold_usado: 0.9}))} />)
    expect(screen.getByText(/Ninguna señal supera su umbral/)).toHaveTextContent('no descarta enfermedad')
  })
  it('no aplica umbrales inventados a resultados históricos', () => {
    render(<ListaPatologias patologias={scores} />)
    expect(screen.getByText(/Resultado histórico sin umbrales/)).toBeInTheDocument()
    expect(screen.queryByRole('list', {name: 'Señales sobre umbral'})).not.toBeInTheDocument()
  })
  it('incluye igualdad de umbral y descarta scores no válidos', () => {
    const result = partitionFindings({ A: 0.5, B: NaN, C: 2 }, [{ etiqueta: 'A', threshold_usado: 0.5 }])
    expect(result.candidates.map((row) => row.name)).toEqual(['A'])
    expect(result.rows).toHaveLength(1)
  })
  it('explica datos ausentes', () => {
    render(<ListaPatologias patologias={{}} />)
    expect(screen.getByText(/No hay puntuaciones disponibles/)).toBeInTheDocument()
  })
})
