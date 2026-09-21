import api from './axios'

export const getPacientes = (params, config = {}) => api.get('/pacientes/', { ...config, params })
export const buscarPacientes = (q) => api.get('/pacientes/buscar/', { params: { q } })
export const createPaciente = (data) => api.post('/pacientes/', data)
export const getPaciente = (id) => api.get(`/pacientes/${id}/`)
export const updatePaciente = (id, data) => api.patch(`/pacientes/${id}/`, data)

export const getEstudios = (params) => api.get('/pacientes/estudios/', { params })
export const createEstudio = (data) => api.post('/pacientes/estudios/', data)
export const getEstudio = (id) => api.get(`/pacientes/estudios/${id}/`)

export const deletePaciente = id => api.delete(`/pacientes/${id}/`)
