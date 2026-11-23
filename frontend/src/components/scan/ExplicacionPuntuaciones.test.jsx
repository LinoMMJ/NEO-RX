import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ExplicacionPuntuaciones from './ExplicacionPuntuaciones'

const findings = [
  {
    etiqueta_en: 'Effusion', etiqueta: 'Derrame pleural', tipo_salida: 'prioritaria',
    probabilidad_estimada: 0.82, threshold_usado: 0.7, decision_habilitada: true, detectado: true,
  },
  {
    etiqueta_en: 'CategoryPleural', etiqueta: 'Categoría pleural', tipo_salida: 'categoria',
    probabilidad_estimada: 0.61, threshold_usado: 0.65, decision_habilitada: true, detectado: false,
  },
]

describe('ExplicacionPuntuaciones', () => {
  it('separa una enfermedad de una categoría y explica el criterio de cada una', () => {
    render(<ExplicacionPuntuaciones hallazgos={findings} />)
    expect(screen.getByText('Derrame pleural').closest('article')).toHaveTextContent('Enfermedad específica')
    expect(screen.getByText('Derrame pleural').closest('article')).toHaveTextContent('Superó su criterio técnico por 12.0 puntos')
    expect(screen.getByText('Categoría pleural').closest('article')).toHaveTextContent('Categoría amplia')
    expect(screen.getByText('Categoría pleural').closest('article')).toHaveTextContent('No equivale a una enfermedad única')
  })

  it('muestra la ubicación solo para la salida cuyo Grad-CAM fue seleccionado', () => {
    render(<ExplicacionPuntuaciones hallazgos={findings} patologiaSeleccionada="Effusion"
      gradCAM={{ resumen_activacion: {
        disponible: true,
        descripcion: 'La influencia se concentra en el tercio inferior y lado izquierdo.',
        cobertura_relativa_pct: 8.4,
        referencia_espacial: 'sectores de la imagen mostrada',
      } }} />)
    expect(screen.getByText(/La influencia se concentra en el tercio inferior/)).toBeInTheDocument()
    expect(screen.getByText(/Zona de activación más intensa: 8.4%/)).toBeInTheDocument()
  })

  it('permite solicitar la localización de cada salida por separado', () => {
    const change = vi.fn()
    render(<ExplicacionPuntuaciones hallazgos={findings} onPatologiaChange={change} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Ver dónde influyó esta salida' })[1])
    expect(change).toHaveBeenCalledWith('CategoryPleural')
  })
})
