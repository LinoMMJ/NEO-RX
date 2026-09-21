import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { uploadDicom, getGradCAM, obtenerEstadoTarea } from '../api/estudios'
import { createEstudio, getPaciente } from '../api/pacientes'
import { useToast } from '../context/useToast'

import ZonaUpload from '../components/scan/ZonaUpload'
import AnimacionCNN from '../components/scan/AnimacionCNN'
import PanelResultados from '../components/scan/PanelResultados'
import BuscadorPaciente from '../components/scan/BuscadorPaciente'
import ProyeccionBadge from '../components/scan/ProyeccionBadge'
import Button from '../components/ui/Button'
import useObjectUrl from '../hooks/useObjectUrl'

// Reverse map español → inglés para Grad-CAM
const ES_A_EN = {
  'Neumonía':             'Pneumonia',
  'Consolidación':        'Consolidation',
  'Infiltrado pulmonar':  'Infiltration',
  'Opacidad pulmonar':    'Lung Opacity',
  'Lesión pulmonar':      'Lung Lesion',
  'Derrame pleural':      'Effusion',
  'Neumotórax':           'Pneumothorax',
  'Engrosamiento pleural':'Pleural_Thickening',
  'Atelectasia':          'Atelectasis',
  'Enfisema':             'Emphysema',
  'Fibrosis pulmonar':    'Fibrosis',
  'Edema pulmonar':       'Edema',
  'Nódulo pulmonar':      'Nodule',
  'Masa pulmonar':        'Mass',
}

export default function EscaneoPage() {
  const navigate = useNavigate()
  const [query] = useSearchParams()
  const pacienteId = query.get('paciente')
  const toast = useToast()
  const [fase, setFase] = useState('upload')   // upload | procesando | resultados | borrosidad
  const [archivo, setArchivo] = useState(null)

  const [paciente, setPaciente] = useState(null)
  useEffect(() => {if(!pacienteId)return;let active=true;getPaciente(pacienteId).then(({data})=>{if(active)setPaciente(data)}).catch(()=>{});return ()=>{active=false}},[pacienteId])
  const [observaciones, setObservaciones] = useState('')
  const [proyeccion, setProyeccion] = useState(null)   // detectada tras el upload

  // Resultado del análisis
  const [resultado, setResultado] = useState(null)
  const [gradCAM, setGradCAM] = useState(null)
  const [gradCAMCargando, setGradCAMCargando] = useState(false)
  const [gradCAMError, setGradCAMError] = useState(false)
  const [patologiaSeleccionada, setPatologiaSeleccionada] = useState(null)
  const [estudioId, setEstudioId] = useState(null)
  const draftStudy = useRef(null)
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

  // Imagen preview para AnimacionCNN
  const imagenPreviewUrl = useObjectUrl(archivo)

  // Carga Grad-CAM (timeout 2min configurado en axios); si falla marca error sin romper UI
  const cargarGradCAM = (imagenId, englishName) => {
    setPatologiaSeleccionada(englishName)
    setGradCAM(null)
    setGradCAMCargando(true)
    setGradCAMError(false)
    getGradCAM(imagenId, englishName)
      .then(({ data: gc }) => { setGradCAM(gc); setGradCAMError(false) })
      .catch(() => { setGradCAM(null); setGradCAMError(true) })
      .finally(() => setGradCAMCargando(false))
  }

  const esperarResultadoTarea = async (taskId, imagenId) => {
    const maxIntentos = 180  // 3 minutos máx (180 × 1s)
    for (let i = 0; i < maxIntentos; i++) {
      await new Promise(r => setTimeout(r, 1000))
      try {
        const { data: r } = await obtenerEstadoTarea(taskId)

        if (r.status === 'FAILURE') {
          toast.error('Error en el análisis CNN. Intenta de nuevo.')
          setFase('upload')
          return
        }

        if (r.status === 'SUCCESS') {
          setProgreso(100)
          if (r.proyeccion) setProyeccion(r.proyeccion)
          setResultado(r)
          setFase('resultados')
          if (r.advertencia_proyeccion) toast.info(r.advertencia_proyeccion)
          const topPatologia = r.patologias ? Object.keys(r.patologias)[0] : null
          const topEnglish = topPatologia ? ES_A_EN[topPatologia] : null
          if (imagenId && topEnglish) cargarGradCAM(imagenId, topEnglish)
          return
        }
        // PENDING / STARTED: seguir esperando (la barra de progreso sigue animando sola)
      } catch {
        // error de red transitorio — seguir intentando
      }
    }
    toast.error('El análisis tardó demasiado. Intenta de nuevo.')
    setFase('upload')
  }

  const handleIniciarAnalisis = async () => {
    if (!archivo || !pacienteValido) return
    setProgreso(0)
    setFase('procesando')
    setProgreso(5)

    try {
      // 1. Crear estudio (la proyección la detecta el backend tras el upload)
      let currentId = draftStudy.current?.patientId === paciente.id ? draftStudy.current.id : null
      if (!currentId) {
        const { data: est } = await createEstudio({
          paciente: paciente.id,
          fecha: new Date().toISOString().split('T')[0],
          tipo_estudio: 'Radiografía de Tórax',
          observaciones,
        })
        currentId = est.id
        draftStudy.current = { id: currentId, patientId: paciente.id }
      }
      setEstudioId(currentId)

      // 2. Upload DICOM/PNG + análisis CNN
      const formData = new FormData()
      formData.append('archivo', archivo)
      formData.append('estudio_id', currentId)

      const { data } = await uploadDicom(formData, (e) => {
        if (e.total) setProgreso(5 + Math.round((e.loaded / e.total) * 15))
      })

      // Borrosidad detectada — respuesta inmediata, sin CNN
      if (data.alerta === 'borrosidad') {
        setProgreso(100)
        if (data.proyeccion) setProyeccion(data.proyeccion)
        setResultado(data)
        setFase('borrosidad')
        return
      }

      // Resultado directo (sin Redis/Celery — inferencia síncrona en backend)
      if (data.status === 'SUCCESS') {
        setProgreso(100)
        if (data.proyeccion) setProyeccion(data.proyeccion)
        setResultado(data)
        setFase('resultados')
        const topPatologia = data.patologias ? Object.keys(data.patologias)[0] : null
        const topEnglish = topPatologia ? ES_A_EN[topPatologia] : null
        if (data.imagen_id && topEnglish) cargarGradCAM(data.imagen_id, topEnglish)
        return
      }

      // 202 Accepted — Celery procesando en background
      if (data.status === 'procesando') {
        if (data.proyeccion) setProyeccion(data.proyeccion)
        await esperarResultadoTarea(data.task_id, data.imagen_id)
        return
      }
    } catch (e) {
      const msg = e.response?.data?.error
      if (e.response) toast.error(msg || 'No se pudo completar el análisis. Intenta nuevamente.')
      else toast.red()
      setFase('upload')
    }
  }

  const handlePatologiaChange = (englishName) => {
    if (!resultado?.imagen_id) return
    cargarGradCAM(resultado.imagen_id, englishName)
  }

  const reiniciar = ({ reuse = false } = {}) => {
    if (!reuse) draftStudy.current = null
    setFase('upload'); setArchivo(null); setResultado(null)
    setGradCAM(null); setGradCAMError(false); setProyeccion(null)
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
                    placeholder="Anotaciones clínicas adicionales..."
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 font-body text-sm resize-none
                      focus:outline-none focus:ring-2 focus:ring-teal-med/40"
                  />
                </div>
              </div>
            </div>

            {/* Zona de upload */}
            <div className="flex flex-col gap-4">
              <ZonaUpload archivo={archivo} onArchivo={setArchivo} />

              <Button
                variant="navy"
                className="w-full text-base py-3.5"
                disabled={!archivo || !pacienteValido}
                onClick={handleIniciarAnalisis}
              >
                Analizar radiografía
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
              <Button variant="secondary" onClick={() => reiniciar({ reuse: true })}>
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
