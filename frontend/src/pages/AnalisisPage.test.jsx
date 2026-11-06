import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import AnalisisPage from './AnalisisPage'
import { getEstudio } from '../api/pacientes'
import { getResultado, reintentarImagen } from '../api/estudios'

vi.mock('../api/pacientes', () => ({ getEstudio: vi.fn() }))
vi.mock('../api/estudios', () => ({ getResultado: vi.fn(), reintentarImagen: vi.fn() }))
vi.mock('../context/useAuth', () => ({ useAuth: () => ({ rol: 'medico' }) }))
vi.mock('../hooks/useGradCAM', () => ({ default: () => ({}) }))
vi.mock('../components/scan/PanelResultados', () => ({ default: () => <div>Resultado del modelo</div> }))
vi.mock('../components/scan/VisorImagen', () => ({ default: () => <div>Radiografía guardada</div> }))

function show() {
  return render(<MemoryRouter initialEntries={['/analisis/7']}><Routes>
    <Route path="/analisis/:id" element={<AnalisisPage />} />
  </Routes></MemoryRouter>)
}

beforeEach(() => {
  getEstudio.mockResolvedValue({ data: { id: 7, ultima_imagen_id: 12, estado: 'pendiente', paciente_nombre: 'Prueba' } })
})

it('la imagen borrosa guardada no aparece eternamente pendiente', async () => {
  getResultado.mockResolvedValue({ data: {
    estado_procesamiento: 'sin_analisis', apta_para_cnn: true,
    clasificacion_imagen: 'chest_xray', motivo_no_cnn: 'Calidad técnica insuficiente por borrosidad.',
  } })
  show()
  expect(await screen.findByText('Radiografía guardada sin CNN')).toBeInTheDocument()
  expect(screen.getByText('Calidad técnica insuficiente por borrosidad.')).toBeInTheDocument()
  expect(screen.queryByText('Análisis pendiente')).not.toBeInTheDocument()
})

it('reintenta una imagen fallida sin realizar una nueva carga', async () => {
  getResultado.mockResolvedValueOnce({ data: { estado_procesamiento: 'error' } })
    .mockResolvedValue({ data: { estado_procesamiento: 'pendiente' } })
  reintentarImagen.mockResolvedValue({ data: { status: 'procesando' } })
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Reintentar análisis' }))
  await waitFor(() => expect(reintentarImagen).toHaveBeenCalledWith(12))
  expect(await screen.findByText('Análisis pendiente')).toBeInTheDocument()
})

it('explica un reintento rechazado y conserva la pantalla', async () => {
  getResultado.mockResolvedValue({ data: { estado_procesamiento: 'error' } })
  reintentarImagen.mockRejectedValue({ response: { data: { error: 'El archivo original no está disponible.' } } })
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Reintentar análisis' }))
  expect(await screen.findByText('El archivo original no está disponible.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Reintentar análisis' })).toBeEnabled()
})

it('muestra un análisis procesado aunque no existan hallazgos sobre el umbral', async () => {
  getEstudio.mockResolvedValue({ data: {
    id: 7, ultima_imagen_id: 12, estado: 'completado', paciente_nombre: 'Prueba', informe_id: 4,
  } })
  getResultado.mockResolvedValue({ data: {
    id: 9,
    estado_procesamiento: 'procesado',
    patologias: {},
    hallazgos: [],
    decision: { estado: 'indeterminado', titulo: 'Sin evidencia suficiente' },
  } })
  show()
  expect(await screen.findByText('Resultado del modelo')).toBeInTheDocument()
  expect(screen.queryByText('Análisis pendiente')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Abrir informe' })).toHaveAttribute('href', '/informes/4')
})
