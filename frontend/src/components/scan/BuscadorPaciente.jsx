import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Plus, X, UserCheck, ArrowLeft, Loader2 } from 'lucide-react'
import { buscarPacientes, createPaciente } from '../../api/pacientes'
import { useToast } from '../../context/useToast'

const GENERO_LABEL = { M: 'Masculino', F: 'Femenino', Otro: 'Otro' }

import { errorMessage, fieldErrors } from '../../api/errors'
import { calcularEdad } from './patientUtils'

// ── Reglas de validación ──
const RE_NOMBRE = /^[\p{L}\p{M} '’-]+$/u
const RE_CI = /^[A-Za-z0-9 ._-]+$/

function validar(form) {
  const e = {}
  if (!form.nombres.trim()) e.nombres = 'Requerido'
  else if (!RE_NOMBRE.test(form.nombres.trim())) e.nombres = 'Solo letras y espacios'
  if (!form.apellidos.trim()) e.apellidos = 'Requerido'
  else if (!RE_NOMBRE.test(form.apellidos.trim())) e.apellidos = 'Solo letras y espacios'
  if (!form.ci.trim()) e.ci = 'Requerido'
  else if (!RE_CI.test(form.ci.trim())) e.ci = 'Use letras, números, espacios o guiones'
  else if (form.ci.trim().length > 20) e.ci = 'Máximo 20 caracteres'
  if (!form.fecha_nacimiento) e.fecha_nacimiento = 'Requerido'
  else {
    const f = new Date(form.fecha_nacimiento)
    const hoy = new Date()
    if (f > hoy) e.fecha_nacimiento = 'No puede ser futura'
    else if (calcularEdad(form.fecha_nacimiento) > 120) e.fecha_nacimiento = 'Fecha no válida (>120 años)'
  }
  if (!form.genero) e.genero = 'Requerido'
  return e
}

const FORM_VACIO = { nombres: '', apellidos: '', ci: '', fecha_nacimiento: '', genero: 'M' }

/**
 * BuscadorPaciente — Autocomplete real con debounce + alta de paciente.
 * Llama onSelect(paciente) cuando hay un paciente seleccionado o creado.
 */
export default function BuscadorPaciente({ seleccionado, onSelect }) {
  const toast = useToast()
  const [modo, setModo] = useState('buscar')   // buscar | nuevo
  const [query, setQuery] = useState('')
  const [resultados, setResultados] = useState([])
  const [buscando, setBuscando] = useState(false)
  const [abierto, setAbierto] = useState(false)
  const [sinResultados, setSinResultados] = useState(false)

  const [form, setForm] = useState(FORM_VACIO)
  const [errores, setErrores] = useState({})
  const [tocado, setTocado] = useState({})
  const [creando, setCreando] = useState(false)

  const boxRef = useRef(null)

  // ── Debounce 400ms ──
  useEffect(() => {
    if (modo !== 'buscar' || seleccionado) return
    const q = query.trim()
    let active = true
    const t = setTimeout(async () => {
      if (q.length < 2) { setResultados([]); setSinResultados(false); setAbierto(false); setBuscando(false); return }
      setBuscando(true)
      try {
        const {data} = await buscarPacientes(q)
        if (!active) return
        const lista = Array.isArray(data) ? data : data.results || []
        setResultados(lista); setSinResultados(lista.length === 0); setAbierto(true)
      } catch { if (active) {toast.red(); setAbierto(false)} }
      finally { if (active) setBuscando(false) }
    }, 400)
    return () => {active = false; clearTimeout(t)}
  }, [query, modo, seleccionado, toast])

  // Cerrar dropdown al clicar fuera
  useEffect(() => {
    const fn = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setAbierto(false) }
    document.addEventListener('mousedown', fn)
    return () => document.removeEventListener('mousedown', fn)
  }, [])

  const elegir = (p) => {
    onSelect(p)
    setAbierto(false)
    setQuery('')
  }

  const irANuevo = () => {
    setModo('nuevo')
    setAbierto(false)
    setForm(() => ({ ...FORM_VACIO, nombres: '', ci: /^\d/.test(query) ? query.trim() : '' }))
    setErrores({}); setTocado({})
  }

  const setCampo = (k, v) => {
    const next = { ...form, [k]: v }
    setForm(next)
    if (tocado[k]) setErrores(validar(next))
  }

  const blur = (k) => {
    setTocado((t) => ({ ...t, [k]: true }))
    setErrores(validar(form))
  }

  const guardar = async () => {
    const e = validar(form)
    setErrores(e)
    setTocado({ nombres: true, apellidos: true, ci: true, fecha_nacimiento: true, genero: true })
    if (Object.keys(e).length) {document.getElementById(`scan-patient-${Object.keys(e)[0]}`)?.focus(); return}
    setCreando(true)
    try {
      const { data } = await createPaciente({
        ...form,
        nombres: form.nombres.trim(),
        apellidos: form.apellidos.trim(),
        ci: form.ci.trim(),
      })
      toast.success('Paciente registrado correctamente.')
      onSelect(data)          // selecciona automáticamente el creado
      setModo('buscar')
      setForm(FORM_VACIO)
    } catch (err) {
      const details = fieldErrors(err); setErrores(details); document.getElementById(`scan-patient-${Object.keys(details)[0]}`)?.focus(); toast.error(errorMessage(err))
    } finally {
      setCreando(false)
    }
  }

  // ── Paciente seleccionado: tarjeta resumen ──
  if (seleccionado) {
    const edad = calcularEdad(seleccionado.fecha_nacimiento)
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        className="rounded-xl border border-success/30 bg-success/5 p-4"
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-success/15 flex items-center justify-center flex-shrink-0">
              <UserCheck className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="font-heading font-bold text-navy text-base leading-tight">
                {seleccionado.nombres} {seleccionado.apellidos}
              </p>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 font-body text-xs text-slate-500">
                <span className="font-mono">CI: {seleccionado.ci}</span>
                <span>{seleccionado.fecha_nacimiento}{edad != null && ` · ${edad} años`}</span>
                <span>{GENERO_LABEL[seleccionado.genero] || seleccionado.genero}</span>
              </div>
            </div>
          </div>
          <button
            onClick={() => onSelect(null)}
            className="p-1.5 rounded-lg text-slate-600 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
            aria-label="Deseleccionar paciente"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </motion.div>
    )
  }

  // ── MODO NUEVO ──
  if (modo === 'nuevo') {
    const campos = [
      { k: 'nombres', label: 'Nombres', type: 'text', ph: 'Ej: Juan Carlos' },
      { k: 'apellidos', label: 'Apellidos', type: 'text', ph: 'Ej: García López' },
      { k: 'ci', label: 'CI', type: 'text', ph: 'Número de identificación', mono: true },
      { k: 'fecha_nacimiento', label: 'Fecha de nacimiento', type: 'date' },
    ]
    return (
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
        <button
          onClick={() => { setModo('buscar'); setErrores({}); setTocado({}) }}
          className="flex items-center gap-1.5 text-xs font-semibold text-sky-800 hover:underline cursor-pointer"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Volver a búsqueda
        </button>
        <div className="flex items-center gap-2 text-teal-med">
          <Plus className="w-4 h-4" />
          <p className="font-body text-sm font-semibold">Registrar nuevo paciente</p>
        </div>

        {campos.map(({ k, label, type, ph, mono }) => (
          <div key={k}>
            <label htmlFor={`scan-patient-${k}`} className="label">
              {label} <span className="text-danger">*</span>
            </label>
            <input
              id={`scan-patient-${k}`}
              maxLength={k === "ci" ? 20 : type === "text" ? 100 : undefined}
              type={type}
              value={form[k]}
              onChange={(e) => setCampo(k, e.target.value)}
              onBlur={() => blur(k)}
              placeholder={ph}
              max={type === 'date' ? new Date().toISOString().split('T')[0] : undefined}
              className={`w-full px-3 py-2 rounded-lg border font-body text-sm transition-all
                focus:outline-none focus:ring-2 focus:ring-teal-med/40 ${mono ? 'font-mono' : ''}
                ${errores[k] ? 'border-danger/60 bg-danger/5' : 'border-slate-200 focus:border-teal-med'}`}
              aria-invalid={!!errores[k]}
              aria-describedby={errores[k] ? `scan-error-${k}` : undefined}
            />
            {errores[k] && <p id={`scan-error-${k}`} className="text-sm text-red-700 mt-1">{String(errores[k])}</p>}
          </div>
        ))}

        <div>
          <label htmlFor="scan-patient-genero" className="label">
            Género <span className="text-danger">*</span>
          </label>
          <select id="scan-patient-genero"
            value={form.genero}
            onChange={(e) => setCampo('genero', e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-slate-200 font-body text-sm
              focus:outline-none focus:ring-2 focus:ring-teal-med/40"
          >
            <option value="M">Masculino</option>
            <option value="F">Femenino</option>
            <option value="Otro">Otro</option>
          </select>
        </div>

        <button
          onClick={guardar}
          disabled={creando}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-sky-700 text-white
            font-heading font-semibold text-sm hover:brightness-110 transition-all cursor-pointer
            disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {creando ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          {creando ? 'Registrando...' : 'Registrar y seleccionar'}
        </button>
      </motion.div>
    )
  }

  // ── MODO BUSCAR ──
  return (
    <div ref={boxRef} className="relative">
      <label htmlFor="scan-patient-search" className="label">
        Paciente <span className="text-danger">*</span>
      </label>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
        <input id="scan-patient-search" aria-expanded={abierto} aria-controls="patient-search-results"
          onKeyDown={e => {if(e.key === "Escape") setAbierto(false); if(e.key === "ArrowDown") {e.preventDefault(); boxRef.current?.querySelector("ul button")?.focus()}}}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => resultados.length && setAbierto(true)}
          placeholder="Buscar por nombre o CI..."
          className="w-full pl-9 pr-9 py-2.5 rounded-xl border border-slate-200 font-body text-sm text-navy
            focus:outline-none focus:ring-2 focus:ring-teal-med/40 focus:border-teal-med transition-all"
          aria-label="Buscar paciente"
          autoComplete="off"
        />
        {buscando && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-teal-med animate-spin" />}
      </div>

      <AnimatePresence>
        {abierto && (resultados.length > 0 || sinResultados) && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="absolute z-30 left-0 right-0 mt-2 bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden"
          >
            {resultados.length > 0 ? (
              <ul id="patient-search-results" className="max-h-72 overflow-y-auto divide-y divide-slate-50">
                {resultados.map((p) => {
                  const edad = calcularEdad(p.fecha_nacimiento)
                  return (
                    <li key={p.id}>
                      <button
                        onClick={() => elegir(p)}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-teal-med/5 transition-colors cursor-pointer"
                      >
                        <span className="flex-1 min-w-0">
                          <span className="block font-body text-sm font-semibold text-navy truncate">
                            {p.nombres} {p.apellidos}
                          </span>
                          <span className="block font-mono text-[11px] text-slate-600">CI: {p.ci}</span>
                        </span>
                        {edad != null && (
                          <span className="font-mono text-xs text-slate-600 flex-shrink-0">{edad} años</span>
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <div className="px-4 py-4 text-center">
                <p className="font-body text-sm text-slate-500 mb-2">No encontrado.</p>
                <button
                  onClick={irANuevo}
                  className="inline-flex items-center gap-1.5 text-sm font-semibold text-sky-800 hover:underline cursor-pointer"
                >
                  <Plus className="w-4 h-4" /> ¿Crear nuevo paciente?
                </button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <button
        onClick={irANuevo}
        className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-teal-med transition-colors cursor-pointer"
      >
        <Plus className="w-3.5 h-3.5" /> Registrar nuevo paciente
      </button>
    </div>
  )
}
