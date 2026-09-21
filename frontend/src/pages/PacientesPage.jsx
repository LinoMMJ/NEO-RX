import { useState, useEffect, useRef } from 'react'
import { Users, Plus, Edit, Trash2 } from 'lucide-react'
import { createPaciente, updatePaciente, deletePaciente } from '../api/pacientes'
import { errorMessage, fieldErrors } from '../api/errors'
import { useAuth } from '../context/useAuth'
import { useToast } from '../context/useToast'
import Spinner from '../components/ui/Spinner'
import { useFilters, useResource } from '../hooks/useWorkspace'
import { Filter, ResetFilters, Pagination } from '../components/ui/WorkspaceUI'
import { Link } from 'react-router-dom'
const empty = { nombres: '', apellidos: '', ci: '', fecha_nacimiento: '', genero: 'M', telefono: '' }
const fields = [['nombres', 'Nombres', 'text', 100], ['apellidos', 'Apellidos', 'text', 100], ['ci', 'CI', 'text', 20], ['fecha_nacimiento', 'Fecha de nacimiento', 'date'], ['telefono', 'Teléfono', 'tel', 20]]
export default function PacientesPage() {
  const { rol } = useAuth(), toast = useToast()
  const canEdit = ['medico', 'recepcionista', 'administrador'].includes(rol)
  const { filters, setFilter, reset } = useFilters({page: '1', page_size: '20', ordering: '-created_at'})
  const page = Math.max(1, Number(filters.page) || 1)
  const setPage = value => setFilter('page', String(typeof value === 'function' ? value(page) : value))
  const [revision, setRevision] = useState(0), [editing, setEditing] = useState(null), [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(empty), [busy, setBusy] = useState(false), [deleting, setDeleting] = useState(null)
  const [error, setError] = useState(''), [errors, setErrors] = useState({})
  const formRef = useRef(null), createRef = useRef(null)
  const {data, loading, error: listError} = useResource('/pacientes/', filters, revision)
  const patients = data?.results || [], total = data?.count ?? 0
  useEffect(() => { if (showForm) { formRef.current?.scrollIntoView({ behavior: 'auto', block: 'start' }); formRef.current?.querySelector('input')?.focus() } }, [showForm, editing])
  function open(patient = null) {
    setEditing(patient); setForm(patient ? Object.fromEntries(Object.keys(empty).map(key => [key, patient[key] || ''])) : { ...empty })
    setError(''); setErrors({}); setShowForm(true)
  }
  function close() { setShowForm(false); createRef.current?.focus() }
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(''); setErrors({})
    try {
      if (editing) await updatePaciente(editing.id, form)
      else await createPaciente(form)
      toast.success(editing ? 'Paciente actualizado.' : 'Paciente registrado.')
      close(); setRevision(v => v + 1)
    } catch (err) { const details = fieldErrors(err); setError(errorMessage(err)); setErrors(details); const key = Object.keys(details)[0]; document.getElementById(`patient-${key}`)?.focus() }
    finally { setBusy(false) }
  }
  async function remove(patient) {
    if (!window.confirm(`¿Eliminar a ${patient.nombres} ${patient.apellidos} y sus estudios no firmados? Los pacientes con informes firmados no pueden eliminarse.`)) return
    setDeleting(patient.id)
    try { await deletePaciente(patient.id); toast.success('Paciente eliminado.'); if (patients.length === 1 && page > 1) setPage(v => v - 1); setRevision(v => v + 1) }
    catch (err) { toast.error(errorMessage(err, 'No se pudo eliminar el paciente.')) }
    finally { setDeleting(null) }
  }
  return <div className="workspace">
    <header className="page-heading">
      <div><h1 className="font-heading font-bold text-navy text-3xl">Pacientes</h1><p className="text-slate-500 text-sm mt-1">{loading ? 'Cargando pacientes…' : `${total} resultados con los filtros actuales`}</p></div>
      {canEdit && <button ref={createRef} onClick={() => open()} className="btn-primary flex items-center gap-2 min-h-11"><Plus size={18} />Nuevo paciente</button>}
    </header>
    {showForm && <section ref={formRef} aria-labelledby="patient-form-title" className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <h2 id="patient-form-title" className="text-xl font-bold text-navy mb-4">{editing ? 'Editar paciente' : 'Registrar paciente'}</h2>
      {error && <p role="alert" className="bg-red-50 text-red-700 p-3 rounded-lg mb-4">{error}</p>}
      <form onSubmit={submit} className="space-y-4">
        <div className="grid sm:grid-cols-2 gap-4">
          {fields.map(([key, label, type, maxLength]) => <div key={key}>
            <label htmlFor={`patient-${key}`} className="block text-sm font-semibold text-navy mb-1">{label}{key !== 'telefono' && ' *'}</label>
            <input id={`patient-${key}`} type={type} maxLength={maxLength} max={type === 'date' ? new Date().toISOString().slice(0, 10) : undefined} value={form[key]} onChange={e => setForm(v => ({ ...v, [key]: e.target.value }))} className="input w-full" required={key !== 'telefono'} aria-invalid={!!errors[key]} aria-describedby={errors[key] ? `error-${key}` : undefined} />
            {errors[key] && <p id={`error-${key}`} className="text-red-700 text-sm mt-1">{String(errors[key])}</p>}
          </div>)}
          <div><label htmlFor="patient-genero" className="block text-sm font-semibold text-navy mb-1">Género *</label><select id="patient-genero" value={form.genero} onChange={e => setForm(v => ({ ...v, genero: e.target.value }))} className="input w-full"><option value="M">Masculino</option><option value="F">Femenino</option><option value="Otro">Otro</option></select></div>
        </div>
        <div className="flex gap-3 justify-end"><button type="button" className="btn-secondary min-h-11" onClick={close} disabled={busy}>Cancelar</button><button className="btn-primary min-h-11" disabled={busy}>{busy ? 'Guardando…' : editing ? 'Actualizar paciente' : 'Registrar paciente'}</button></div>
      </form>
    </section>}
    <section className="filters" aria-label="Filtros de pacientes">
      <Filter label="Nombre o CI" name="search" value={filters.search} onChange={setFilter} placeholder="Buscar pacientes…"/>
      <Filter label="Género" name="genero" value={filters.genero} onChange={setFilter}><option value="">Todos</option><option value="M">Masculino</option><option value="F">Femenino</option><option value="Otro">Otro</option></Filter>
      <Filter label="Registrado desde" name="fecha_desde" value={filters.fecha_desde} type="date" onChange={setFilter}/>
      <Filter label="Registrado hasta" name="fecha_hasta" value={filters.fecha_hasta} type="date" onChange={setFilter}/>
      <Filter label="Orden" name="ordering" value={filters.ordering} onChange={setFilter}><option value="-created_at">Más recientes</option><option value="created_at">Más antiguos</option><option value="apellidos,nombres">Apellido y nombre</option><option value="fecha_nacimiento">Fecha de nacimiento</option></Filter>
      <Filter label="Por página" name="page_size" value={filters.page_size} onChange={setFilter}><option value="10">10 pacientes</option><option value="20">20 pacientes</option><option value="50">50 pacientes</option></Filter>
      <ResetFilters onClick={reset}/>
    </section>
    {listError ? <div role="alert" className="bg-red-50 p-4 text-red-700 rounded-xl">{listError}<button className="underline ml-3" onClick={() => setRevision(v => v + 1)}>Reintentar</button></div> : loading ? <div role="status" className="flex justify-center py-12"><Spinner size="lg" color="navy" /><span className="sr-only">Cargando pacientes</span></div> : !patients.length ? <div className="text-center py-12 text-slate-500"><Users className="mx-auto mb-3" />No se encontraron pacientes.</div> : <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
      <div className="overflow-x-auto"><table className="data-table"><thead className="bg-slate-50 text-slate-600"><tr>{['Nombre completo', 'CI', 'Nacimiento', 'Género', 'Teléfono', 'Acciones'].map(label => <th scope="col" key={label} className="text-left p-4">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{patients.map(patient => <tr key={patient.id}>
        <td className="p-4 font-semibold text-navy">{patient.nombres} {patient.apellidos}<Link className="block text-xs text-sky-800 underline underline-offset-4 font-normal mt-1" to={`/estudios?paciente=${patient.id}`}>Consultar estudios</Link></td><td className="p-4">{patient.ci}</td><td className="p-4 whitespace-nowrap">{patient.fecha_nacimiento}</td><td className="p-4">{patient.genero}</td><td className="p-4">{patient.telefono || '—'}</td>
        <td className="p-4">{canEdit && <div className="flex gap-2"><button aria-label={`Editar a ${patient.nombres}`} onClick={() => open(patient)} className="btn-secondary min-h-11 px-3"><Edit size={16} /></button><button aria-label={`Eliminar a ${patient.nombres}`} disabled={deleting !== null} onClick={() => remove(patient)} className="min-h-11 px-3 rounded-lg border border-red-200 text-red-700 disabled:opacity-50"><Trash2 size={16} /></button></div>}</td>
      </tr>)}</tbody></table></div>
      <Pagination page={page} pageSize={filters.page_size} total={total} onChange={setFilter}/>
    </div>}
  </div>
}
