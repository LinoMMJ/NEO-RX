import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, Archive, CheckCircle2, ShieldX } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { uploadDicom, obtenerEstadoTarea, previsualizarDicom } from '../api/estudios'
import { getPaciente } from '../api/pacientes'
import { useToast } from '../context/useToast'

import ZonaUpload from '../components/scan/ZonaUpload'
import AnimacionCNN from '../components/scan/AnimacionCNN'
import PanelResultados from '../components/scan/PanelResultados'
import BuscadorPaciente from '../components/scan/BuscadorPaciente'
import ProyeccionBadge from '../components/scan/ProyeccionBadge'
import Button from '../components/ui/Button'
import useObjectUrl from '../hooks/useObjectUrl'
import useGradCAM from '../hooks/useGradCAM'

const normalizarResultado = (data) => {
  const raw = data?.patologias
  if (!raw || !Array.isArray(raw.hallazgos)) return data
  const patologias = Object.fromEntries(
    raw.hallazgos
      .filter((item) => item && Number.isFinite(Number(item.probabilidad_estimada)))
      .map((item) => [item.etiqueta, Number(item.probabilidad_estimada)])
  )
  return {
    ...data,
    patologias,
    modelo: data.modelo || raw.modelo,
    es_fine_tuned: data.es_fine_tuned ?? raw.es_fine_tuned,
    thresholds: data.thresholds || raw.thresholds,
    nota_modelo: data.nota_modelo || raw.nota,
  }
}

export default function EscaneoPage() {
  const navigate = useNavigate()
  const [query] = useSearchParams()
  const pacienteId = query.get('paciente')
  const toast = useToast()
  const [fase, setFase] = useState('upload')   // upload | procesando | resultados | borrosidad | guardada | rechazada
  const [archivo, setArchivo] = useState(null)
  const [dicomPreview, setDicomPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const [paciente, setPaciente] = useState(null)
  useEffect(() => {if(!pacienteId)return;let active=true;getPaciente(pacienteId).then(({data})=>{if(active)setPaciente(data)}).catch(()=>{});return ()=>{active=false}},[pacienteId])
  const [observaciones, setObservaciones] = useState('')
  const [proyeccion, setProyeccion] = useState(null)   // detectada tras el upload

  // Resultado del análisis
  const [resultado, setResultado] = useState(null)
  const maps = useGradCAM()
  const { data: gradCAM, loading: gradCAMCargando, error: gradCAMError, pathology: patologiaSeleccionada } = maps
  const [estudioId, setEstudioId] = useState(null)
  const [progreso, setProgreso] = useState(0)

  // Animación de progreso simulado — llega a 85% máx y espera respuesta del backend
  useEffect(() => {
    if (fase !== 'procesando') return
    const intervalos = [
      setTimeout(() => setProgreso(15), 600),
      setTimeout(() => setProgreso(35), 1800),
      setTimeout(() => setProgreso(55), 3200),
      setTimeout(() => setProgreso(72), 5000),
      setTimeout(() => setProgreso(82), 7000),
      setTimeout(() => setProgreso(85), 15000),
    ]
    return () => intervalos.forEach(clearTimeout)
  }, [fase])

  const pacienteValido = !!paciente

  // El navegador no puede dibujar DICOM directamente. Para DICOM se usa la
  // miniatura segura devuelta por el backend; PNG/JPG/WebP siguen usando URL local.
  const objectPreviewUrl = useObjectUrl(archivo)
  const archivoEsDicom = Boolean(archivo?.name?.toLowerCase().match(/\.(dcm|dicom)$/))
  const imagenPreviewUrl = archivoEsDicom ? dicomPreview : objectPreviewUrl

  const handleArchivo = async (nuevoArchivo) => {
    setArchivo(nuevoArchivo)
    setDicomPreview(null)
    if (!nuevoArchivo || !nuevoArchivo.name?.toLowerCase().match(/\.(dcm|dicom)$/)) return

    setPreviewLoading(true)
    try {
      const { data } = await previsualizarDicom(nuevoArchivo)
      setDicomPreview(data.preview_url)
    } catch {
      toast.error('No se pudo crear la vista previa DICOM. Puedes elegir otro archivo.')
    } finally {
      setPreviewLoading(false)
    }
  }

  const esperarResultadoTarea = async (taskId, savedStudyId) => {
    const maxIntentos = 90
    for (let i = 0; i < maxIntentos; i++) {
      await new Promise(r => setTimeout(r, 1000))
      try {
        const { data: r } = await obtenerEstadoTarea(taskId)

        if (r.status === 'FAILURE') {
          toast.error('Error en el análisis CNN. Intenta de nuevo.')
          setFase('upload')
          return
        }

        if (r.status === 'STORED') {
          setProgreso(100)
          if (r.estudio_id) setEstudioId(r.estudio_id)
          setResultado(r)
          setFase('guardada')
          return
        }

        if (r.status === 'SUCCESS') {
          setProgreso(100)
          if (r.estudio_id) setEstudioId(r.estudio_id)
          if (r.proyeccion) setProyeccion(r.proyeccion)
          const resultadoNormalizado = normalizarResultado(r)
          setResultado(resultadoNormalizado)
          setFase('resultados')
          if (r.advertencia_proyeccion) toast.info(r.advertencia_proyeccion)
          return
        }
        // PENDING / STARTED: seguir esperando (la barra de progreso sigue animando sola)
      } catch {
        // error de red transitorio — seguir intentando
      }
    }
    toast.info('El estudio está guardado y continúa pendiente. Puedes consultar su estado sin volver a subir la imagen.')
    navigate(`/analisis/${savedStudyId}`)
  }

  const handleIniciarAnalisis = async () => {
    if (!archivo || !pacienteValido) return
    setProgreso(0)
    setResultado(null)
    maps.reset()
    setFase('procesando')
    setProgreso(5)

    try {
      const formData = new FormData()
      formData.append('archivo', archivo)
      formData.append('paciente_id', paciente.id)
      formData.append('observaciones', observaciones)

      const { data } = await uploadDicom(formData, (event) => {
        if (event.total) setProgreso(5 + Math.round((event.loaded / event.total) * 15))
      })

      if (data.estudio_id) setEstudioId(data.estudio_id)

      if (data.alerta === 'borrosidad') {
        setProgreso(100)
        if (data.proyeccion) setProyeccion(data.proyeccion)
        setResultado(data)
        setFase('borrosidad')
        return
      }

      if (data.status === 'STORED') {
        setProgreso(100)
        setResultado(data)
        setFase('guardada')
        return
      }

      if (data.status === 'SUCCESS') {
        setProgreso(100)
        if (data.proyeccion) setProyeccion(data.proyeccion)
        const resultadoNormalizado = normalizarResultado(data)
        setResultado(resultadoNormalizado)
        setFase('resultados')
        return
      }

      if (data.status === 'procesando') {
        if (data.proyeccion) setProyeccion(data.proyeccion)
        await esperarResultadoTarea(data.task_id, data.estudio_id)
      }
    } catch (error) {
      const response = error.response?.data
      if (response?.status === 'REJECTED' || response?.codigo === 'no_radiografia') {
        setResultado(response)
        setFase('rechazada')
        return
      }
      const details = Array.isArray(response?.detalles) ? response.detalles.join(' ') : ''
      const message = [response?.error, details].filter(Boolean).join(': ')
      if (error.response) toast.error(message || 'No se pudo validar la radiografía. Intenta nuevamente.')
      else toast.error('No se pudo conectar con el servidor. Verifica que el backend esté iniciado.')
      if (response?.estudio_id) {
        navigate(`/analisis/${response.estudio_id}`)
        return
      }
      setFase('upload')
    }
  }

  const handlePatologiaChange = (englishName) => {
    if (!resultado?.imagen_id) return
    maps.load(resultado.imagen_id, englishName)
  }

  const reiniciar = () => {
    setFase('upload'); setArchivo(null); setDicomPreview(null); setResultado(null)
    maps.reset(); setProyeccion(null)
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="font-heading font-bold text-navy text-3xl tracking-tight">Nuevo estudio</h1>
        <p className="font-body text-slate-500 text-sm mt-1">Carga de radiografía y análisis asistido; la interpretación médica requiere revisión profesional.</p>
      </div>

      <AnimatePresence mode="wait">
        {/* ═══ FASE 1: UPLOAD ═══ */}
        {fase === 'upload' && (
          <motion.div
            key="upload"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="grid grid-cols-1 lg:grid-cols-2 gap-6"
          >
            {/* Formulario paciente */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-5">
              <h2 className="font-heading font-bold text-navy text-base">Datos del paciente</h2>

              <BuscadorPaciente seleccionado={paciente} onSelect={setPaciente} />

              <div className="border-t border-slate-100 pt-4 space-y-4">
                {/* Tipo de estudio — informativo, solo lectura */}
                <div>
                  <label className="font-body text-xs font-semibold text-slate-500 block mb-1.5">
                    Tipo de estudio
                  </label>
                  <ProyeccionBadge proyeccion={proyeccion} />
                </div>

                <div>
                  <label className="font-body text-xs font-semibold text-slate-500 block mb-1">
                    Observaciones (opcional)
                  </label>
                  <textarea id="scan-observaciones" aria-label="Observaciones clínicas"
                    value={observaciones}
                    onChange={(e) => setObservaciones(e.target.value)}
                    rows={2}
                    placeholder="Anotaciones clínicas adicionales…"
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 font-body text-sm resize-none
                      focus:outline-none focus:ring-2 focus:ring-teal-med/40"
                  />
                </div>
              </div>
            </div>

            {/* Zona de upload */}
            <div className="flex flex-col gap-4">
              <ZonaUpload
                archivo={archivo}
                onArchivo={handleArchivo}
                previewUrl={archivoEsDicom ? dicomPreview : objectPreviewUrl}
                previewLoading={previewLoading}
              />

              <Button
                variant="navy"
                className="w-full text-base py-3.5"
                disabled={!archivo || !pacienteValido}
                onClick={handleIniciarAnalisis}
              >
                Validar y continuar
              </Button>

              {(!archivo || !pacienteValido) && (
                <p className="font-body text-xs text-slate-400 text-center">
                  {!pacienteValido ? 'Busca o registra un paciente primero' : 'Selecciona un archivo de imagen'}
                </p>
              )}
            </div>
          </motion.div>
        )}

        {/* ═══ FASE 2: PROCESANDO ═══ */}
        {fase === 'procesando' && (
          <motion.div
            key="procesando"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
          >
            <AnimacionCNN imagenPreview={imagenPreviewUrl} progreso={progreso} completado={false} />
          </motion.div>
        )}

        {/* ═══ FASE: RADIOGRAFÍA GUARDADA SIN CNN ═══ */}
        {fase === 'guardada' && resultado && (
          <motion.section
            key="guardada"
            initial={{ opacity: 0, y: 16, filter: 'blur(6px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            className="mx-auto max-w-2xl overflow-hidden rounded-2xl border border-sky-300/40 bg-white shadow-xl shadow-sky-950/5"
            aria-live="polite"
          >
            <div className="flex items-start gap-4 bg-sky-50 px-6 py-5">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-sky-600 text-white shadow-lg shadow-sky-600/20">
                <Archive className="h-6 w-6" aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <h2 className="font-heading text-xl font-bold text-navy">Radiografía guardada</h2>
                <p className="mt-1 font-body text-sm leading-6 text-slate-600">
                  Se vinculó al expediente del paciente. No se ejecutó la CNN porque el modelo está validado únicamente para tórax.
                </p>
              </div>
            </div>
            <dl className="grid gap-4 px-6 py-5 sm:grid-cols-2">
              <div><dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Región identificada</dt><dd className="mt-1 font-semibold text-navy">{resultado.clasificacion?.anatomical_region || 'No determinada'}</dd></div>
              <div><dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Estado</dt><dd className="mt-1 flex items-center gap-2 font-semibold text-sky-700"><CheckCircle2 className="h-4 w-4" /> Almacenada sin análisis CNN</dd></div>
              <div className="sm:col-span-2"><dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Motivo</dt><dd className="mt-1 text-sm text-slate-600">{resultado.clasificacion?.reason || resultado.mensaje}</dd></div>
            </dl>
            <div className="flex flex-wrap gap-3 border-t border-slate-100 px-6 py-4">
              <Button variant="primary" onClick={() => navigate('/estudios')}>Ver estudios</Button>
              <Button variant="secondary" onClick={reiniciar}>Cargar otra radiografía</Button>
            </div>
          </motion.section>
        )}

        {/* ═══ FASE: ARCHIVO RECHAZADO ═══ */}
        {fase === 'rechazada' && resultado && (
          <motion.section
            key="rechazada"
            initial={{ opacity: 0, y: 16, filter: 'blur(6px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            className="mx-auto max-w-2xl overflow-hidden rounded-2xl border border-rose-300/50 bg-white shadow-xl shadow-rose-950/5"
            aria-live="assertive"
          >
            <div className="flex items-start gap-4 bg-rose-50 px-6 py-5">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-rose-600 text-white shadow-lg shadow-rose-600/20">
                <ShieldX className="h-6 w-6" aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <h2 className="font-heading text-xl font-bold text-rose-950">Archivo no admitido</h2>
                <p className="mt-1 font-body text-sm leading-6 text-rose-900/75">
                  {resultado.error || 'La imagen no corresponde a una radiografía válida.'}
                </p>
              </div>
            </div>
            <div className="space-y-3 px-6 py-5 text-sm text-slate-600">
              <p>{resultado.clasificacion?.reason}</p>
              <p className="rounded-xl bg-slate-50 px-4 py-3 font-medium text-slate-700">
                No se creó ningún estudio ni se almacenó el archivo. Usa una radiografía DICOM, PNG o JPG legible.
              </p>
            </div>
            <div className="border-t border-slate-100 px-6 py-4">
              <Button variant="secondary" onClick={reiniciar}>Seleccionar otro archivo</Button>
            </div>
          </motion.section>
        )}

        {/* ═══ FASE: BORROSIDAD ═══ */}
        {fase === 'borrosidad' && (
          <motion.div
            key="borrosidad"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-xl mx-auto"
          >
            <div className="bg-danger/10 border-2 border-danger/40 rounded-2xl p-8 text-center">
              <AlertTriangle className="w-16 h-16 text-danger mx-auto mb-4" />
              <h2 className="font-heading font-bold text-danger text-2xl mb-2">
                Borrosidad cinética detectada
              </h2>
              <p className="font-mono text-sm text-danger/80 mb-2">
                Varianza de Laplaciano: {resultado?.varianza?.toFixed(2)} (umbral: 100.0)
              </p>
              <p className="font-body text-slate-600 mb-6">
                Esta imagen no es apta para diagnóstico por IA.
                Solicite una nueva toma con menor movimiento del paciente.
              </p>
              <Button variant="secondary" onClick={reiniciar}>
                Intentar con nueva imagen
              </Button>
            </div>
          </motion.div>
        )}

        {/* ═══ FASE 3: RESULTADOS ═══ */}
        {fase === 'resultados' && resultado && (
          <motion.div key="resultados" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            {proyeccion && (
              <div className="mb-4">
                <ProyeccionBadge proyeccion={proyeccion} />
              </div>
            )}
            <PanelResultados
              resultado={resultado}
              gradCAM={gradCAM}
              gradCAMCargando={gradCAMCargando}
              gradCAMError={gradCAMError}
              estudioId={estudioId}
              informeId={resultado?.informe_id}
              patologiaSeleccionada={patologiaSeleccionada}
              onPatologiaChange={handlePatologiaChange}
              onInformeGenerado={(inf) => navigate(`/informes/${inf.id}`)}
            />
            <div className="mt-6 flex justify-center">
              <Button variant="secondary" onClick={reiniciar}>
                Nuevo análisis
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
