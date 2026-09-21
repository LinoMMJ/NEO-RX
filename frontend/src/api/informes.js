import api from './axios'

export const generarInforme = (estudioId) =>
  api.post('/informes/generar/', { estudio_id: estudioId })

export const getInforme = (id) => api.get(`/informes/${id}/`)

export const updateInforme = (id, data) => api.patch(`/informes/${id}/`, data)

export const descargarInformePDF = (id) =>
  api.get(`/informes/${id}/pdf/`, { responseType: 'blob', timeout: 30000 })
