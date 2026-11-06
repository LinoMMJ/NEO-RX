import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import InformePage from './InformePage'
import { getInforme, descargarInformePDF, updateInforme } from '../api/informes'

vi.mock('../api/informes', () => ({ getInforme: vi.fn(), updateInforme: vi.fn(), descargarInformePDF: vi.fn() }))
vi.mock('../context/useAuth', () => ({ useAuth: () => ({ user: 'medico', rol: 'medico' }) }))
vi.mock('../context/useToast', () => ({ useToast: () => ({ error: vi.fn(), success: vi.fn(), red: vi.fn() }) }))
vi.mock('../hooks/useGradCAM', () => ({ default: () => ({}) }))
vi.mock('../components/scan/VisorImagen', () => ({ default: () => <div>Radiografía</div> }))

const data = { id: 7, estudio: 3, estado: 'borrador', paciente: {}, tecnica: 'Técnica',
  hallazgos: 'Hallazgos', correlacion_clinica: 'Correlación', impresion: 'Impresión', recomendaciones: 'Recomendaciones' }

function show() {
  return render(<MemoryRouter initialEntries={['/informes/7']}><Routes>
    <Route path="/informes/:id" element={<InformePage />} />
  </Routes></MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  getInforme.mockResolvedValue({ data })
  descargarInformePDF.mockResolvedValue({ data: new Blob(['%PDF-test'], { type: 'application/pdf' }) })
  URL.createObjectURL = vi.fn(() => 'blob:test')
  URL.revokeObjectURL = vi.fn()
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
})

it('permite descargar el preinforme al terminar el estudio sin firmarlo', async () => {
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Descargar preinforme (PDF)' }))
  await waitFor(() => expect(descargarInformePDF).toHaveBeenCalledWith('7', true))
})

it('exige guardar los cambios antes de exportar el contenido', async () => {
  show()
  const button = await screen.findByRole('button', { name: 'Descargar preinforme (PDF)' })
  fireEvent.change(screen.getAllByRole('textbox')[0], { target: { value: 'Edición pendiente' } })
  expect(button).toBeDisabled()
  fireEvent.click(button)
  expect(descargarInformePDF).not.toHaveBeenCalled()
})

it('mantiene la descarga definitiva para un informe firmado', async () => {
  getInforme.mockResolvedValue({ data: { ...data, estado: 'firmado' } })
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Descargar informe firmado (PDF)' }))
  await waitFor(() => expect(descargarInformePDF).toHaveBeenCalledWith('7', false))
})

it('sincroniza el texto normalizado al revisar y firma solo el contenido guardado', async () => {
  updateInforme.mockResolvedValueOnce({ data: { ...data, estado: 'revisado' } })
    .mockResolvedValueOnce({ data: { ...data, estado: 'firmado', fecha_firmado: '2026-10-27T12:00:00Z' } })
  show()
  const review = await screen.findByRole('button', { name: 'Marcar como revisado' })
  fireEvent.change(screen.getAllByRole('textbox')[0], { target: { value: '  Técnica  ' } })
  fireEvent.click(review)
  const sign = screen.getByRole('button', { name: 'Firmar informe' })
  await waitFor(() => expect(sign).toBeEnabled())
  expect(screen.getAllByRole('textbox')[0]).toHaveValue('Técnica')
  fireEvent.click(sign)
  fireEvent.click(screen.getByRole('button', { name: 'Firmar', exact: true }))
  await screen.findByRole('button', { name: 'Descargar informe firmado (PDF)' })
  expect(updateInforme).toHaveBeenLastCalledWith('7', { estado: 'firmado' })
  expect(screen.getAllByRole('textbox')[0]).toBeDisabled()
})

it('mantiene bloqueada la firma de una plantilla pendiente de revisión médica', async () => {
  getInforme.mockResolvedValue({ data: { ...data, estado: 'revisado', hallazgos: '[Describir los hallazgos]' } })
  show()
  expect(await screen.findByRole('button', { name: 'Firmar informe' })).toBeDisabled()
  expect(updateInforme).not.toHaveBeenCalled()
})
