import VisorImagen from '../components/scan/VisorImagen'
import useGradCAM from '../hooks/useGradCAM'
import { formatModelScore } from '../utils/modelScore'
import { partitionFindings } from '../utils/modelFindings'
import { errorMessage } from '../api/errors'
import { useState, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Save, CheckCircle, PenLine, ChevronDown, BarChart3, FileText,
  User, AlertTriangle, ShieldCheck, X, Download, Activity, Clock3, BrainCircuit,
} from 'lucide-react'
import { getInforme, updateInforme, descargarInformePDF } from '../api/informes'
import { useAuth } from '../context/useAuth'
import { useToast } from '../context/useToast'
import { calcularEdad } from '../components/scan/patientUtils'
import Spinner from '../components/ui/Spinner'

const ESTADO_BADGE = {
  borrador: 'bg-teal-med/15 text-teal-med border-teal-med/30',
  revisado: 'bg-orange-500/15 text-orange-600 border-orange-500/30',
  firmado:  'bg-success/15 text-success border-success/30',
}
const GENERO_LABEL = { M: 'Masculino', F: 'Femenino', Otro: 'Otro' }
const PROY_LABEL = { PA: 'PA · Postero-Anterior', AP: 'AP · Antero-Posterior', LAT: 'Lateral' }

// Cada sección anatómica con su acento de color (estilo informe médico real)
const SECCIONES = [
  { key: 'tecnica',         label: 'Técnica',                rows: 2 },
  { key: 'hallazgos',       label: 'Hallazgos Radiológicos', rows: 9, probs: true },
  { key: 'correlacion_clinica', label: 'Correlación Clínico-Radiológica', rows: 5 },
  { key: 'impresion',       label: 'Impresión Diagnóstica',  rows: 4 },
  { key: 'recomendaciones', label: 'Recomendaciones',        rows: 3 },
]

const PASOS_ESTUDIO = [
  ['Carga', 'Imagen registrada'],
  ['IA', 'CNN procesada'],
  ['Borrador', 'Informe creado'],
  ['Revisión', 'Validación médica'],
  ['Firma', 'Informe definitivo'],
]

function isCompleted(value) {
  const text = String(value || '').trim()
  return text.length > 0 && !/\[(describir|valorar|completar)[^\]]*\]/i.test(text)
}

export default function InformePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const toast = useToast()

  const [informe, setInforme] = useState(null)
  const [form, setForm] = useState({})
  const [loading, setLoading] = useState(!!id)
  const [guardando, setGuardando] = useState(null)   // 'borrador' | 'revisado' | 'firmado' | null
  const [showProbs, setShowProbs] = useState(false)
  const [confirmar, setConfirmar] = useState(false)
  const [descargando, setDescargando] = useState(false)
  const maps = useGradCAM()
  const dirty = informe && Object.keys(form).some((key) => form[key] !== (informe[key] || ''))
  useEffect(() => {
    if (!dirty) return
    const warn = (event) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  useEffect(() => {
    if (!id) return
    getInforme(id)
      .then(({ data }) => {
        setInforme(data)
        setForm({
          tecnica: data.tecnica || '',
          hallazgos: data.hallazgos || '',
          correlacion_clinica: data.correlacion_clinica || '',
          impresion: data.impresion || '',
          recomendaciones: data.recomendaciones || '',
        })
      })
      .catch((e) => {
        if (!e.response) toast.red()
        else { toast.error('No se pudo cargar el informe.'); navigate('/dashboard') }
      })
      .finally(() => setLoading(false))
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const firmado = informe?.estado === 'firmado'

  const handleDescargarPDF = async () => {
    setDescargando(true)
    try {
      const { data: blob } = await descargarInformePDF(id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Informe_${informe.paciente?.ci || id}_Estudio${informe.estudio}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 200)
    } catch (e) {
      let msg = 'No se pudo generar el PDF.'
      if (e.response?.data instanceof Blob) {
        try {
          const text = await e.response.data.text()
          const json = JSON.parse(text)
          if (json.error) msg = json.error
        } catch { /* blob no era JSON */ }
      } else if (e.response?.data?.error) {
        msg = e.response.data.error
      }
      toast.error(msg)
    } finally {
      setDescargando(false)
    }
  }

  const guardar = async (estado) => {
    setGuardando(estado)
    try {
      const { data } = await updateInforme(id, { ...form, estado })
      setInforme(data)
      const msg = {
        borrador: 'Borrador guardado.',
        revisado: 'Informe marcado como revisado.',
        firmado: 'Informe firmado correctamente.',
      }
      toast.success(msg[estado])
    } catch (e) {
      if (e.response) toast.error(errorMessage(e, 'No se pudo guardar el informe.'))
      else toast.red()
    } finally {
      setGuardando(null)
      setConfirmar(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Spinner size="xl" color="navy" /></div>
  }

  if (!id || !informe) {
    return (
      <div className="max-w-md mx-auto mt-20 text-center">
        <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
          <FileText className="w-7 h-7 text-slate-400" />
        </div>
        <h2 className="font-heading font-bold text-navy text-xl">Sin informe seleccionado</h2>
        <p className="font-body text-slate-500 text-sm mt-2">
          Genera un informe desde un análisis para verlo aquí.
        </p>
      </div>
    )
  }

  const p = informe.paciente || {}
  const edad = calcularEdad(p.fecha_nacimiento)
  const proy = informe.proyeccion?.tipo || 'PA'
  const probs = informe.probabilidades || {}
  const { rows: probsList, candidates } = partitionFindings(probs, informe.hallazgos_ia)
  const hasThresholds = probsList.some((row) => row.threshold !== null)
  const checklist = [
    ['Técnica verificada', isCompleted(form.tecnica)],
    ['Hallazgos revisados', isCompleted(form.hallazgos)],
    ['Correlación clínica registrada', isCompleted(form.correlacion_clinica)],
    ['Impresión diagnóstica revisada', isCompleted(form.impresion)],
    ['Recomendaciones definidas', isCompleted(form.recomendaciones)],
  ]
  const checklistCompleto = checklist.every(([, done]) => done)
  const pasoActual = informe.estado === 'firmado' ? 4 : informe.estado === 'revisado' ? 3 : 2

  return (
    <div className="clinical-report-page max-w-6xl mx-auto">
      <div className="clinical-report-heading mb-6">
        <Link to={`/analisis/${informe.estudio}`} onClick={(event) => { if (dirty && !window.confirm('Hay cambios sin guardar. ¿Salir del informe?')) event.preventDefault() }} className="inline-flex mb-3 text-sm underline text-teal-med">Volver a la radiografía y al análisis</Link>
        <p className="clinical-eyebrow">EXPEDIENTE RADIOLÓGICO · REVISIÓN MÉDICA</p>
        <h1 className="font-heading font-bold text-navy text-3xl tracking-tight">Informe Radiológico</h1>
        <p className="font-body text-slate-500 text-sm mt-1">Neo Rayos X Digital · Pre-informe asistido por CNN</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-6">
        {/* ════ COLUMNA IZQUIERDA: imagen + paciente ════ */}
        <aside className="space-y-4 lg:sticky lg:top-20 self-start">
          <div className="bg-scan-bg rounded-2xl border border-slate-200 shadow-sm p-4">
            <VisorImagen imagenUrl={informe.imagen_png_url} patologias={informe.probabilidades}
              analysisEnabled={Boolean(informe.imagen_origen)} gradCAM={maps.data}
              gradCAMCargando={maps.loading} gradCAMError={maps.error}
              patologiaSeleccionada={maps.pathology}
              onPatologiaChange={(name) => maps.load(informe.imagen_origen, name)} />
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-4">
              <User className="w-4 h-4 text-teal-med" />
              <h3 className="font-heading font-bold text-navy text-sm">Datos del paciente</h3>
            </div>
            <dl className="space-y-2.5 font-body text-sm">
              {[
                ['Nombre', `${p.nombres || ''} ${p.apellidos || ''}`.trim() || '—'],
                ['CI', p.ci || '—', true],
                ['Fecha nac.', p.fecha_nacimiento ? `${p.fecha_nacimiento}${edad != null ? ` · ${edad} años` : ''}` : '—'],
                ['Género', GENERO_LABEL[p.genero] || p.genero || '—'],
              ].map(([k, v, mono]) => (
                <div key={k} className="flex justify-between gap-3">
                  <dt className="text-slate-400">{k}</dt>
                  <dd className={`text-navy font-medium text-right ${mono ? 'font-mono' : ''}`}>{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        </aside>

        {/* ════ COLUMNA DERECHA: formulario ════ */}
        <div className="space-y-5">
          {/* Encabezado de solo lectura */}
          <div className="rounded-2xl border border-blue-200 bg-blue-50/60 p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-heading font-bold text-navy text-sm tracking-wide">
                INFORME RADIOLÓGICO — Neo Rayos X Digital
              </h2>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold border capitalize ${ESTADO_BADGE[informe.estado]}`}>
                {informe.estado}
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2 font-body text-xs">
              {[
                ['Paciente', `${p.nombres || ''} ${p.apellidos || ''}`.trim() || '—'],
                ['CI', p.ci || '—'],
                ['Fecha', informe.estudio_fecha || informe.fecha_creacion?.split('T')[0] || '—'],
                ['Proyección', PROY_LABEL[proy] || proy],
                ['Nro. Estudio', `#${informe.estudio}`],
              ].map(([k, v]) => (
                <div key={k}>
                  <p className="text-slate-400">{k}</p>
                  <p className="text-navy font-semibold mt-0.5">{v}</p>
                </div>
              ))}
            </div>
          </div>

          {firmado && (
            <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-success/10 border border-success/30 text-success">
              <ShieldCheck className="w-4 h-4 flex-shrink-0" />
              <p className="font-body text-sm">Informe firmado — solo lectura. Esta versión es definitiva.</p>
            </div>
          )}

          <section className="grid gap-3 md:grid-cols-[1.05fr_1fr]" aria-label="Resumen del estudio">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <BrainCircuit className="h-4 w-4 text-blue-600" />
                  <h2 className="font-heading text-xs font-bold uppercase tracking-wider text-slate-600">Apoyo de IA</h2>
                </div>
                <span className="rounded-full border border-slate-200 px-2.5 py-1 text-xs font-bold text-slate-600">Revisión médica</span>
              </div>
              <div className="mt-3 flex items-end gap-3">
                <span className="font-mono text-2xl font-bold text-navy">{hasThresholds ? candidates.length : '—'}</span>
                <span className="pb-1 text-xs text-slate-500">señales sobre su umbral</span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-500">{!hasThresholds ? 'Resultado histórico sin umbrales conservados.' : candidates.length > 1 ? 'Múltiples señales; la IA no permite escoger un diagnóstico único.' : candidates.length === 1 ? 'Señal pendiente de confirmar en la imagen.' : 'Sin señales sobre umbral; no descarta enfermedad.'} No determina urgencia.</p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2"><Activity className="h-4 w-4 text-teal-med" /><h2 className="font-heading text-xs font-bold uppercase tracking-wider text-slate-600">Trazabilidad del estudio</h2></div>
              <ol className="mt-4 grid grid-cols-5 gap-1" aria-label="Estado del flujo clínico">
                {PASOS_ESTUDIO.map(([title, detail], index) => {
                  const complete = index <= pasoActual
                  const current = index === pasoActual
                  return <li key={title} className="min-w-0">
                    <div className={`h-1 rounded-full ${complete ? 'bg-teal-med' : 'bg-slate-200'}`} />
                    <p className={`mt-2 text-[10px] font-bold leading-tight ${current ? 'text-navy' : complete ? 'text-teal-med' : 'text-slate-400'}`}>{title}</p>
                    <p className="mt-0.5 hidden text-[9px] leading-tight text-slate-400 lg:block">{detail}</p>
                  </li>
                })}
              </ol>
            </div>
          </section>

          {/* Secciones del informe */}
          {SECCIONES.map(({ key, label, rows, probs: hasProbs }) => (
            <div key={key}>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor={key} className="font-heading text-[11px] font-bold text-slate-500 tracking-widest uppercase">
                  {label}
                </label>
                {hasProbs && (
                  <button
                    onClick={() => setShowProbs((s) => !s)}
                    className="flex items-center gap-1.5 text-xs font-semibold text-teal-med hover:underline cursor-pointer"
                    aria-expanded={showProbs}
                  >
                    <BarChart3 className="w-3.5 h-3.5" /> Puntuaciones CNN
                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showProbs ? 'rotate-180' : ''}`} />
                  </button>
                )}
              </div>

              <div className={hasProbs && showProbs ? 'grid lg:grid-cols-[1fr_auto] gap-3' : ''}>
                <textarea
                  id={key}
                  value={form[key]}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  rows={rows}
                  disabled={firmado}
                  className={`w-full px-4 py-3 rounded-lg border border-slate-200
                    font-body text-sm text-navy leading-relaxed resize-y bg-white transition-colors
                    focus:outline-none focus:ring-2 focus:ring-teal-med/40 focus:ring-offset-1
                    disabled:bg-slate-50 disabled:text-slate-500 disabled:resize-none
                    ${key === 'hallazgos' ? 'whitespace-pre-wrap font-mono text-[13px]' : ''}`}
                />

                {/* Panel colapsable de probabilidades CNN, junto a Hallazgos */}
                <AnimatePresence>
                  {hasProbs && showProbs && (
                    <motion.div
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: 'auto' }}
                      exit={{ opacity: 0, width: 0 }}
                      className="lg:w-64 rounded-lg border border-slate-200 bg-slate-50 p-4 overflow-hidden"
                    >
                      <p className="font-heading text-[10px] font-bold text-slate-400 tracking-widest uppercase mb-3">
                        Salida del modelo
                      </p>
                      {probsList.length === 0 ? (
                        <p className="font-body text-xs text-slate-400">No hay puntuaciones disponibles.</p>
                      ) : (
                        <div className="space-y-2.5">
                          <p className="text-xs text-slate-500">Activación /100, no certeza diagnóstica.</p>
                          {probsList.map(({ name, score, threshold, above }) => (
                            <div key={name}>
                              <div className="flex justify-between items-baseline mb-0.5">
                                <span className="font-body text-[11px] text-navy">{name}</span>
                                <span className="font-mono text-[11px] font-bold text-slate-600">{formatModelScore(score)}</span>
                              </div>
                              <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                <motion.div
                                  className={`h-full rounded-full ${above ? 'bg-teal-med' : 'bg-slate-400'}`}
                                  initial={{ width: 0 }}
                                  animate={{ width: `${score * 100}%` }}
                                  transition={{ duration: 0.6, ease: 'easeOut' }}
                                />
                              </div>
                              <p className="mt-1 text-[10px] text-slate-500">{threshold === null ? 'Sin umbral registrado' : `${above ? 'Sobre' : 'Bajo'} umbral ${formatModelScore(threshold)}`}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          ))}

          {/* Firma */}
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-5">
            <p className="font-heading text-[11px] font-bold text-slate-500 tracking-widest uppercase mb-3">Firma</p>
            <div className="grid grid-cols-2 gap-4 font-body text-sm mb-5">
              <div>
                <p className="text-slate-400 text-xs">Médico Radiólogo</p>
                <p className="text-navy font-semibold mt-0.5">{informe.medico_nombre || user || '—'}</p>
              </div>
              <div>
                <p className="text-slate-400 text-xs">Fecha de firma</p>
                <p className="text-navy font-semibold mt-0.5 font-mono">
                  {informe.fecha_firmado ? new Date(informe.fecha_firmado).toLocaleString('es-BO') : '—'}
                </p>
              </div>
            </div>

            {!firmado && (
              <div className="mb-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center gap-2"><Clock3 className="h-4 w-4 text-teal-med" /><h3 className="font-heading text-xs font-bold uppercase tracking-wider text-slate-600">Checklist previo a la firma</h3></div>
                <ul className="mt-3 grid gap-2 sm:grid-cols-2" aria-label="Checklist clínico">
                  {checklist.map(([label, done]) => <li key={label} className={`flex items-center gap-2 text-xs ${done ? 'text-emerald-700' : 'text-slate-500'}`}>
                    <CheckCircle className={`h-4 w-4 flex-none ${done ? 'text-emerald-600' : 'text-slate-300'}`} />{label}
                  </li>)}
                </ul>
                {!checklistCompleto && <p className="mt-3 text-xs text-amber-700">Completa las secciones marcadas antes de firmar el informe.</p>}
              </div>
            )}

            {firmado && (
              <div className="mb-4">
                <button
                  onClick={handleDescargarPDF}
                  disabled={descargando}
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-lg
                    bg-success text-white font-heading font-semibold text-sm shadow-md
                    hover:brightness-110 hover:scale-[1.01] transition-all cursor-pointer
                    disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {descargando ? <Spinner size="sm" color="white" /> : <Download className="w-4 h-4" />}
                  {descargando ? 'Generando PDF…' : 'Descargar informe firmado (PDF)'}
                </button>
              </div>
            )}

            {!firmado && <p role="status" className="text-sm text-slate-600 mb-3">{dirty ? 'Cambios sin guardar. Guarda y revisa el contenido antes de firmar.' : 'Contenido guardado.'} {!checklistCompleto && ' Completa los campos de la plantilla entre corchetes.'}</p>}
            <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t border-slate-100">
              <button
                onClick={() => guardar('borrador')}
                disabled={firmado || guardando}
                className="flex-1 inline-flex items-center justify-center gap-2 py-2.5 rounded-lg bg-white border border-slate-200
                  text-navy font-heading font-semibold text-sm shadow-sm hover:bg-slate-50 transition-all cursor-pointer
                  disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {guardando === 'borrador' ? <Spinner size="sm" color="navy" /> : <Save className="w-4 h-4" />}
                Guardar borrador
              </button>
              <button
                onClick={() => guardar('revisado')}
                disabled={firmado || guardando}
                className="flex-1 inline-flex items-center justify-center gap-2 py-2.5 rounded-lg bg-teal-med
                  text-white font-heading font-semibold text-sm shadow-md hover:brightness-110 hover:scale-[1.01] transition-all cursor-pointer
                  disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {guardando === 'revisado' ? <Spinner size="sm" color="white" /> : <CheckCircle className="w-4 h-4" />}
                Marcar como revisado
              </button>
              <button
                onClick={() => setConfirmar(true)}
                disabled={firmado || guardando || dirty || informe?.estado !== 'revisado' || !checklistCompleto}
                title={!checklistCompleto ? 'Completa el checklist clínico antes de firmar' : 'Marca el informe como revisado antes de firmar'}
                className="flex-1 inline-flex items-center justify-center gap-2 py-2.5 rounded-lg bg-navy
                  text-white font-heading font-semibold text-sm shadow-md hover:brightness-125 hover:scale-[1.01] transition-all cursor-pointer
                  disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <PenLine className="w-4 h-4" /> Firmar informe
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Modal de confirmación de firma */}
      <AnimatePresence>
        {confirmar && (
          <motion.div
            className="fixed inset-0 z-[900] flex items-center justify-center p-4 bg-navy/50 backdrop-blur-sm"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => !guardando && setConfirmar(false)}
          >
            <motion.div
              role="dialog" aria-modal="true"
              initial={{ opacity: 0, scale: 0.94, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 12 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-full bg-warning/15 flex items-center justify-center flex-shrink-0">
                  <AlertTriangle className="w-5 h-5 text-warning" />
                </div>
                <div className="flex-1">
                  <h3 className="font-heading font-bold text-navy text-lg">¿Confirmar firma del informe?</h3>
                  <p className="font-body text-sm text-slate-500 mt-1.5">
                    Esta acción no puede deshacerse. El informe quedará sellado con tu firma
                    y la fecha actual, y no podrá editarse.
                  </p>
                </div>
                <button
                  onClick={() => setConfirmar(false)}
                  className="text-slate-400 hover:text-navy cursor-pointer" aria-label="Cerrar"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setConfirmar(false)}
                  disabled={!!guardando}
                  className="flex-1 py-2.5 rounded-lg border border-slate-200 text-navy font-heading font-semibold text-sm
                    hover:bg-slate-50 transition-colors cursor-pointer disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  onClick={() => guardar('firmado')}
                  disabled={!!guardando}
                  className="flex-1 inline-flex items-center justify-center gap-2 py-2.5 rounded-lg bg-navy text-white
                    font-heading font-semibold text-sm hover:brightness-125 transition-all cursor-pointer disabled:opacity-60"
                >
                  {guardando === 'firmado' ? <Spinner size="sm" color="white" /> : <PenLine className="w-4 h-4" />}
                  Firmar
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
