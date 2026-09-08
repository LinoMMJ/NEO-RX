import api from './axios'

export const uploadDicom = (formData, onUploadProgress) =>
  api.post('/estudios/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
    timeout: 300000,  // 5min: cubre inferencia CNN síncrona cuando no hay Redis
  })

export const obtenerEstadoTarea = (taskId) =>
  api.get(`/estudios/tarea/${taskId}/`)

export const getImagenDetalle = (id) => api.get(`/estudios/imagen/${id}/`)

export const getGradCAM = (imagenId, pathology = null) =>
  api.get('/diagnostico/gradcam/', {
    params: { imagen_id: imagenId, pathology },
    timeout: 120000,  // 2min: backward pass ResNet-50 en CPU puede tomar 60-90s
  })

export const getResultado = (imagenId) =>
  api.get(`/diagnostico/resultado/${imagenId}/`)
