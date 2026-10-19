import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Archive, CheckCircle2, ClipboardPlus, Database, FileArchive, ShieldCheck, UserRound } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { registrarEstudioSinIA } from '../api/estudios'
import { getPaciente } from '../api/pacientes'
import { useToast } from '../context/useToast'
import BuscadorPaciente from '../components/scan/BuscadorPaciente'
import ZonaUpload from '../components/scan/ZonaUpload'
import Button from '../components/ui/Button'

const TIPOS = [
  'Radiografía de cráneo', 'Radiografía de columna cervical', 'Radiografía de columna dorsal',
  'Radiografía de columna lumbar', 'Radiografía de hombro', 'Radiografía de brazo / antebrazo',
  'Radiografía de mano / muñeca', 'Radiografía de pelvis / cadera', 'Radiografía de rodilla',
  'Radiografía de pierna / tobillo / pie', 'Otra radiografía',
]

export default function RegistroEstudioPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [query] = useSearchParams()
  const [paciente, setPaciente] = useState(null)
  const [archivo, setArchivo] = useState(null)
  const [tipo, setTipo] = useState(TIPOS[0])
  const [otroTipo, setOtroTipo] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [registro, setRegistro] = useState(null)

  useEffect(() => {
    const id = query.get('paciente')
    if (!id) return
    getPaciente(id).then(({ data }) => setPaciente(data)).catch(() => {})
  }, [query])

  const tipoFinal = tipo === 'Otra radiografía' ? otroTipo.trim() : tipo
  const puedeGuardar = Boolean(paciente && archivo && tipoFinal)

  async function guardar() {
    if (!puedeGuardar) return
    setGuardando(true)
    try {
      const body = new FormData()
      body.append('archivo', archivo)
      body.append('paciente_id', paciente.id)
      body.append('tipo_estudio', tipoFinal)
      body.append('observaciones', observaciones.trim())
      body.append('registro_sin_ia', 'true')
      const { data } = await registrarEstudioSinIA(body)
      setRegistro(data)
      toast.success('Estudio registrado en el expediente del paciente.')
    } catch (error) {
      const detail = error.response?.data?.error || error.response?.data?.detalles?.join(' ') || 'No se pudo registrar el estudio.'
      toast.error(detail)
    } finally {
      setGuardando(false)
    }
  }

  if (registro) {
    return <motion.div className="clinical-record-page mx-auto max-w-2xl" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.24, ease: [0.23, 1, 0.32, 1] }}>
      <section className="clinical-success-card overflow-hidden rounded-2xl border border-emerald-200 bg-white shadow-xl shadow-emerald-950/5">
        <div className="flex items-start gap-4 bg-emerald-50 px-6 py-5">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-emerald-600 text-white"><CheckCircle2 className="h-6 w-6" /></div>
          <div><h1 className="font-heading text-xl font-bold text-navy">Estudio registrado sin análisis</h1><p className="mt-1 text-sm leading-6 text-slate-600">El archivo y sus datos quedaron vinculados al expediente del paciente. No se ejecutó CNN, no se creó informe y no requiere firma.</p></div>
        </div>
        <dl className="grid gap-4 px-6 py-5 sm:grid-cols-2">
          <div><dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tipo de estudio</dt><dd className="mt-1 font-semibold text-navy">{tipoFinal}</dd></div>
          <div><dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Estado</dt><dd className="mt-1 font-semibold text-emerald-700">Registrado sin análisis</dd></div>
          <div className="sm:col-span-2"><dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Archivo</dt><dd className="mt-1 text-sm text-slate-600">{archivo?.name}</dd></div>
        </dl>
        <div className="flex flex-wrap gap-3 border-t border-slate-100 px-6 py-4"><Button variant="primary" onClick={() => navigate('/estudios')}>Ver estudios</Button><Button variant="secondary" onClick={() => { setRegistro(null); setArchivo(null); setObservaciones('') }}>Registrar otro</Button></div>
      </section>
    </motion.div>
  }

  return <div className="clinical-record-page mx-auto max-w-5xl">
    <motion.header className="clinical-record-header mb-7" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: [0.23, 1, 0.32, 1] }}>
      <div className="clinical-record-mark"><ClipboardPlus className="h-5 w-5" /></div>
      <div><p className="clinical-eyebrow">ARCHIVO CLÍNICO · SIN PROCESAMIENTO</p><h1 className="font-heading text-3xl font-bold tracking-tight text-navy">Registrar estudio sin IA</h1><p className="mt-1 max-w-2xl text-sm text-slate-500">Archive radiografías no torácicas en el expediente clínico. Este flujo está diseñado para conservar información, no para analizarla.</p></div>
    </motion.header>
    <motion.ol className="clinical-flow mb-6" aria-label="Pasos del registro" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.26, delay: 0.06, ease: [0.23, 1, 0.32, 1] }}>
      {[['01', UserRound, 'Paciente', 'Vincular expediente'], ['02', FileArchive, 'Estudio', 'Describir y adjuntar'], ['03', Database, 'Archivo', 'Guardar sin IA']].map(([number, Icon, title, detail]) => <li key={title} className="clinical-flow-step"><span className="clinical-flow-number">{number}</span><Icon className="h-4 w-4" /><span><strong>{title}</strong><small>{detail}</small></span></li>)}
    </motion.ol>
    <div className="grid gap-6 lg:grid-cols-2">
      <motion.section className="clinical-form-card space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.28, delay: 0.1, ease: [0.23, 1, 0.32, 1] }}>
        <div className="clinical-card-heading"><span>01</span><div><h2 className="font-heading font-bold text-navy">Datos del registro</h2><p>Seleccione el paciente y describa el estudio.</p></div></div>
        <BuscadorPaciente seleccionado={paciente} onSelect={setPaciente} />
        <div className="clinical-field border-t border-slate-100 pt-4"><label htmlFor="tipo-estudio">Tipo de estudio</label><select id="tipo-estudio" value={tipo} onChange={event => setTipo(event.target.value)}>{TIPOS.map(item => <option key={item}>{item}</option>)}</select></div>
        {tipo === 'Otra radiografía' && <div className="clinical-field"><label htmlFor="otro-tipo">Especifique el estudio</label><input id="otro-tipo" value={otroTipo} onChange={event => setOtroTipo(event.target.value)} maxLength="200" placeholder="Ej. Radiografía de codo izquierdo" /></div>}
        <div className="clinical-field"><label htmlFor="registro-observaciones">Observaciones <span>Opcional</span></label><textarea id="registro-observaciones" value={observaciones} onChange={event => setObservaciones(event.target.value)} rows={4} placeholder="Motivo del estudio o notas administrativas…" /></div>
      </motion.section>
      <motion.section className="space-y-4" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.28, delay: 0.14, ease: [0.23, 1, 0.32, 1] }}><div className="clinical-upload-card"><div className="clinical-card-heading"><span>02</span><div><h2 className="font-heading font-bold text-navy">Archivo radiográfico</h2><p>El archivo se conservará en el historial clínico.</p></div></div><ZonaUpload archivo={archivo} onArchivo={setArchivo} title="Adjunta la radiografía" ariaLabel="Zona de carga del estudio sin IA" helpText="Se valida que el archivo sea una radiografía y se archiva en el expediente. Este flujo no ejecuta la CNN ni crea un informe." /></div><div className="clinical-archive-note"><ShieldCheck className="h-5 w-5 shrink-0" /><p><strong>Archivo clínico, sin diagnóstico.</strong> La radiografía quedará disponible en el historial del paciente. No se analiza, diagnostica ni firma este registro.</p></div><Button variant="navy" className="w-full py-3.5 text-base shadow-lg shadow-slate-950/15" disabled={!puedeGuardar || guardando} onClick={guardar}>{guardando ? 'Guardando estudio…' : <><Archive className="h-5 w-5" /> Guardar sin análisis</>}</Button>{!puedeGuardar && <p className="text-center text-xs text-slate-400">Seleccione paciente, tipo de estudio y archivo para continuar.</p>}</motion.section>
    </div>
  </div>
}
