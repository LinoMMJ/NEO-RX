import { RotateCcw } from 'lucide-react'
export function Filter({label, name, value, onChange, children, type = 'text', placeholder}) {
  return <div><label className="label" htmlFor={`filter-${name}`}>{label}</label>{children ? <select className="input" id={`filter-${name}`} value={value || ''} onChange={e => onChange(name,e.target.value)}>{children}</select> : <input className="input" id={`filter-${name}`} type={type} value={value || ''} placeholder={placeholder} onChange={e => onChange(name,e.target.value)}/>}</div>
}
export function ResetFilters({onClick}) {return <button className="btn-secondary" onClick={onClick}><RotateCcw size={16}/>Limpiar filtros</button>}
export function Pagination({page, pageSize, total, onChange}) {
  const current = Math.max(1, Number(page) || 1), size = Math.max(1, Number(pageSize) || 20)
  return <nav className="table-footer" aria-label="Paginación"><span>{total} resultados · Página {current} de {Math.max(1,Math.ceil(total/size))}</span><div className="flex gap-2"><button className="btn-secondary" disabled={current <= 1} onClick={() => onChange('page',String(current-1))}>Anterior</button><button className="btn-secondary" disabled={current*size >= total} onClick={() => onChange('page',String(current+1))}>Siguiente</button></div></nav>
}
export function ResourceState({loading, error, empty, onRetry, children}) {
  if (loading) return <div className="panel empty-state" role="status">Cargando datos…</div>
  if (error) return <div className="error-state" role="alert">{error}<button className="btn-secondary ml-3" onClick={onRetry}>Reintentar</button></div>
  if (empty) return <div className="panel empty-state"><h2>No hay resultados</h2><p>Pruebe otros filtros o amplíe el intervalo de fechas.</p></div>
  return children
}
export function Status({value}) {const labels={pendiente:'Pendiente', en_proceso:'En proceso', completado:'Completado', requiere_repeticion:'Repetición técnica', firmado:'Firmado', borrador:'Borrador', revisado:'Revisado'}; return <span className={`status-pill status-${value}`}>{labels[value] || value || 'Sin informe'}</span>}
