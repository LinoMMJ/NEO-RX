import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ListaPatologias from './ListaPatologias'
import { partitionFindings } from '../../utils/modelFindings'

const scores = { 'Fibrosis pulmonar': 0.78, 'Nódulo pulmonar': 0.71, 'Enfisema': 0.61 }
const findings = Object.keys(scores).map((etiqueta, index) => ({ etiqueta, threshold_usado: [0.5, 0.8, 0.7][index] }))

describe('ListaPatologias', () => {
  it('muestra la categoría sin exponer detalles técnicos del modelo', () => {
    render(<ListaPatologias enfoque={{ modo: 'preentrenado', estado: 'orientacion_categoria', hallazgos_detectados: [] }}
      decision={{ titulo: 'Orientación por categoría: Infecciosa', mensaje: 'Requiere revisión.' }}
      categoria={{ estado: 'seleccionada', nombre: 'Infecciosa', puntuacion_modelo: 0.824 }} />)
    expect(screen.getByLabelText('Categoría orientativa')).toHaveTextContent('Infecciosa')
    expect(screen.getByLabelText('Puntuación del modelo para categoría Infecciosa')).toHaveTextContent('82.4/100')
    expect(screen.queryByText('82.4%')).not.toBeInTheDocument()
    expect(screen.queryByText(/preentrenad/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/modo temporal/i)).not.toBeInTheDocument()
  })

  it('prioriza hasta dos hallazgos sin mostrar categorías competidoras', () => {
    render(<ListaPatologias enfoque={{ estado: 'hallazgos_prioritarios', hallazgos_detectados: [
      { etiqueta_en: 'Effusion', etiqueta: 'Derrame pleural', probabilidad_estimada: 0.88 },
      { etiqueta_en: 'Atelectasis', etiqueta: 'Atelectasia', probabilidad_estimada: 0.83 },
    ] }} decision={{ titulo: 'Hallazgos prioritarios para revisión', mensaje: 'Requieren confirmación.' }} />)
    expect(screen.getByLabelText('Hallazgos prioritarios detectados')).toHaveTextContent('Derrame pleural')
    expect(screen.getByLabelText('Hallazgos prioritarios detectados')).toHaveTextContent('Atelectasia')
    expect(screen.queryByLabelText('Categoría orientativa')).not.toBeInTheDocument()
  })

  it('el respaldo muestra categoría sin inventar enfermedades específicas', () => {
    render(<ListaPatologias enfoque={{ estado: 'orientacion_categoria', hallazgos_detectados: [] }}
      decision={{ titulo: 'Orientación por categoría: Tumoral', mensaje: 'No descarta los hallazgos prioritarios.' }}
      categoria={{ estado: 'seleccionada', nombre: 'Tumoral' }} />)
    expect(screen.getByLabelText('Categoría orientativa')).toHaveTextContent('Tumoral')
    expect(screen.queryByLabelText('Hallazgos prioritarios detectados')).not.toBeInTheDocument()
  })

  it('mantiene compatibilidad con la puntuación técnica de resultados históricos', () => {
    render(<ListaPatologias enfoque={{ estado: 'orientacion_categoria', hallazgos_detectados: [] }}
      decision={{ titulo: 'Orientación por categoría: Intersticial', mensaje: 'Requiere revisión.' }}
      categoria={{ estado: 'seleccionada', nombre: 'Intersticial', puntuacion_tecnica: 0.731 }} />)
    expect(screen.getByLabelText('Puntuación del modelo para categoría Intersticial')).toHaveTextContent('73.1/100')
  })
  it('muestra una conclusión antes de la salida técnica', () => {
    render(<ListaPatologias patologias={scores} hallazgos={findings} alcance={['Neumotórax', 'Derrame pleural', 'Edema pulmonar']} />)
    expect(screen.getByRole('status')).toHaveTextContent('Hallazgo compatible con fibrosis pulmonar')
    expect(screen.getByText('Ver salida técnica para auditoría')).toBeInTheDocument()
    expect(screen.getByText('78.0/100')).toBeInTheDocument()
    expect(screen.queryByText('78.0%')).not.toBeInTheDocument()
    expect(screen.getByText(/El modelo evalúa únicamente/)).toHaveTextContent('Neumotórax')
  })

  it('no inventa un ganador cuando varias clases superan su umbral', () => {
    render(<ListaPatologias patologias={scores} hallazgos={findings.map((f) => ({ ...f, threshold_usado: 0.5 }))} />)
    expect(screen.getByRole('status')).toHaveTextContent('Más de un hallazgo requiere revisión')
    expect(screen.getByRole('status')).toHaveTextContent('no fuerza un diagnóstico único')
  })

  it('no declara normalidad si ninguna clase supera su umbral', () => {
    render(<ListaPatologias patologias={scores} hallazgos={findings.map((f) => ({ ...f, threshold_usado: 0.9 }))} />)
    expect(screen.getByRole('status')).toHaveTextContent('Sin evidencia suficiente')
    expect(screen.getByRole('status')).toHaveTextContent('no descarta enfermedad')
  })

  it('no aplica umbrales inventados a resultados históricos', () => {
    render(<ListaPatologias patologias={scores} />)
    expect(screen.getByRole('status')).toHaveTextContent('Resultado histórico no interpretable')
  })

  it('incluye igualdad de umbral y descarta scores no válidos', () => {
    const result = partitionFindings({ A: 0.5, B: NaN, C: 2 }, [{ etiqueta: 'A', threshold_usado: 0.5 }])
    expect(result.candidates.map((row) => row.name)).toEqual(['A'])
    expect(result.rows).toHaveLength(1)
  })

  it('explica datos ausentes', () => {
    render(<ListaPatologias patologias={{}} />)
    expect(screen.getByRole('status')).toHaveTextContent('Sin resultado disponible')
  })

  it('respeta la abstención explícita del backend', () => {
    const disabled = findings.map((finding) => ({ ...finding, decision_habilitada: false }))
    render(<ListaPatologias patologias={scores} hallazgos={disabled} decision={{ estado: 'modelo_pendiente_validacion', titulo: 'Resultado no concluyente', mensaje: 'Modelo pendiente de validación.' }} />)
    expect(screen.getByRole('status')).toHaveTextContent('Modelo pendiente de validación')
    expect(screen.getAllByText(/Decisión deshabilitada/)).toHaveLength(3)
  })

  it('muestra solo las señales de la categoría seleccionada', () => {
    const category = {
      estado: 'seleccionada', nombre: 'Pleural',
      enfermedades: [
        { etiqueta: 'Derrame pleural', etiqueta_en: 'Effusion', probabilidad_estimada: 0.88 },
        { etiqueta: 'Neumotórax', etiqueta_en: 'Pneumothorax', probabilidad_estimada: 0.21 },
      ],
    }
    render(<ListaPatologias patologias={scores} hallazgos={findings} categoria={category}
      decision={{ estado: 'categoria_detectada', titulo: 'Categoría principal: Pleural', mensaje: 'Requiere revisión.' }} />)
    expect(screen.getByLabelText('Categoría principal')).toHaveTextContent('Pleural')
    expect(screen.getByLabelText('Señales de la categoría Pleural')).toHaveTextContent('Derrame pleural')
    expect(screen.getByLabelText('Señales de la categoría Pleural')).toHaveTextContent('Neumotórax')
    expect(screen.getByText('88.0/100')).toBeInTheDocument()
  })
})
