import api from './axios'

export const uploadDicom = (formData, onUploadProgress) =>
  api.post('/estudios/upload/', formData, {
    onUploadProgress,
    // El navegador genera Content-Type junto con el boundary multipart.
    // La inferencia local usa CPU. No cancelar a los 30 s: Django sigue
    // procesando aunque Axios abandone la respuesta y se crean reintentos
    // que congestionan todavía más el modelo.
    timeout: 180000,
  })

export const previsualizarDicom = (archivo) => {
  const formData = new FormData()
  formData.append('archivo', archivo)
  return api.post('/estudios/vista-previa/', formData, { timeout: 20000 })
}

export const registrarEstudioSinIA = (formData, onUploadProgress) =>
  uploadDicom(formData, onUploadProgress)

export const obtenerEstadoTarea = (taskId) =>
  api.get(`/estudios/tarea/${taskId}/`)

export const getImagenDetalle = (id) => api.get(`/estudios/imagen/${id}/`)

export const getGradCAM = (imagenId, pathology = null, signal) =>
  api.get('/diagnostico/gradcam/', {
    params: { imagen_id: imagenId, pathology },
    signal,
    // Grad-CAM se ejecuta bajo demanda. Si no responde en un minuto, el visor
    // conserva la radiografía original en lugar de quedar bloqueado.
    timeout: 60000,
  })

export const getResultado = (imagenId) =>
  api.get(`/diagnostico/resultado/${imagenId}/`)
