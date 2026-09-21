import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Plus } from 'lucide-react'
import { useAuth } from '../context/useAuth'
import { useFilters, useResource } from '../hooks/useWorkspace'
import { Filter, ResourceState } from '../components/ui/WorkspaceUI'
const today = () => new Date().toLocaleDateString('en-CA')
const startDate = () => {const date=new Date(); date.setDate(date.getDate()-29); return date.toLocaleDateString('en-CA')}
export default function DashboardPage() {
  const {rol}=useAuth(), admin=rol==='administrador'
  const {filters,setFilter}=useFilters({fecha_desde:startDate(),fecha_hasta:today(),vista:'clinica'})
  const [revision,setRevision]=useState(0)
  const range={fecha_desde:filters.fecha_desde,fecha_hasta:filters.fecha_hasta}
  const summary=useResource('/workspace/resumen/',range,revision)
  const recent=useResource('/pacientes/',{page_size:6,ordering:'-created_at'},revision)
  const administration=admin && filters.vista==='administracion'
  const stats=summary.data
  const completed=stats?.estudios_por_estado.find(v=>v.estado==='completado')?.total ?? 0
  const metrics=administration ? [['Usuarios',stats?.administracion?.usuarios_total],['Cuentas activas',stats?.administracion?.usuarios_activos],['Movimientos del período',stats?.administracion?.movimientos_total]] : [['Pacientes registrados',stats?.pacientes_total],['Estudios del período',stats?.estudios_total],['Estudios completados',completed],['Informes sin firmar',stats?.informes_pendientes]]
  return <div className="workspace"><header className="page-heading"><div><h1>Tablero</h1><p>{admin ? 'Operación clínica y control administrativo en un solo lugar.' : rol==='medico' ? 'Pacientes, estudios e informes pendientes de revisión.' : 'Pacientes y seguimiento de la recepción de estudios.'}</p></div><Link className="btn-primary" to={rol==='administrador' ? '/pacientes' : '/escaneo'}><Plus size={18}/>{rol==='administrador' ? 'Gestionar pacientes' : 'Nuevo estudio'}</Link></header>
    {admin && <div className="tabs" aria-label="Vista del tablero">{[['clinica','Operación clínica'],['administracion','Administración']].map(([v,l])=><button key={v} aria-pressed={filters.vista===v} onClick={()=>setFilter('vista',v)}>{l}</button>)}</div>}
    <section className="filters" aria-label="Período del tablero"><Filter label="Registrado desde" name="fecha_desde" value={filters.fecha_desde} type="date" onChange={setFilter}/><Filter label="Registrado hasta" name="fecha_hasta" value={filters.fecha_hasta} type="date" onChange={setFilter}/><p className="text-sm text-slate-600 pb-2">Los pacientes y usuarios muestran el total actual; los estudios y movimientos usan este período.</p></section>
    <ResourceState loading={summary.loading} error={summary.error} onRetry={()=>setRevision(v=>v+1)}><dl className="summary-strip">{metrics.map(([label,value])=><div className="summary-item" key={label}><dt>{label}</dt><dd>{value ?? '—'}</dd></div>)}</dl>
      {administration ? <section className="panel"><div className="panel-heading"><h2>Control de usuarios</h2><Link to="/admin/usuarios" className="btn-secondary">Administrar usuarios<ArrowRight size={16}/></Link></div><div className="p-6 flex flex-wrap gap-8">{stats?.administracion?.usuarios_por_rol.map(item=><div key={item.rol}><p className="text-sm text-slate-600 capitalize">{item.rol}</p><p className="text-2xl font-semibold mt-1">{item.total}</p></div>)}</div><div className="px-6 pb-6"><Link to="/actividad" className="text-sky-800 font-semibold text-sm underline underline-offset-4">Consultar historial de movimientos</Link></div></section> : <section className="panel"><div className="panel-heading"><h2>Trabajo pendiente</h2><Link to="/pendientes" className="btn-secondary">Ver pendientes<ArrowRight size={16}/></Link></div><div className="grid sm:grid-cols-3 gap-6 p-6">{[['Por procesar',stats?.procesamiento_pendiente,'procesamiento'],['Errores de procesamiento',stats?.errores_procesamiento,'errores'],['Repetición técnica',stats?.repeticiones,'repeticion']].map(([label,total,queue])=><Link className="hover:underline" key={queue} to={`/pendientes?cola=${queue}&fecha_desde=${range.fecha_desde}&fecha_hasta=${range.fecha_hasta}`}><p className="text-sm text-slate-600">{label}</p><p className="font-heading text-2xl font-semibold text-navy mt-1">{total ?? '—'}</p></Link>)}</div></section>}
    </ResourceState>
    {!administration && <section className="panel"><div className="panel-heading"><h2>Pacientes registrados recientemente</h2><Link to="/pacientes" className="btn-secondary">Todos los pacientes<ArrowRight size={16}/></Link></div><ResourceState loading={recent.loading} error={recent.error} empty={!recent.data?.results?.length} onRetry={()=>setRevision(v=>v+1)}><div className="table-scroll"><table className="data-table"><thead><tr><th scope="col">Paciente</th><th scope="col">CI</th><th scope="col">Nacimiento</th><th scope="col">Estudios</th></tr></thead><tbody>{recent.data?.results?.map(row=><tr key={row.id}><td className="font-semibold text-navy">{row.nombres} {row.apellidos}</td><td>{row.ci}</td><td className="whitespace-nowrap">{row.fecha_nacimiento}</td><td><Link className="text-sky-800 underline underline-offset-4" to={`/estudios?paciente=${row.id}`}>Consultar estudios</Link></td></tr>)}</tbody></table></div></ResourceState></section>}
  </div>
}
