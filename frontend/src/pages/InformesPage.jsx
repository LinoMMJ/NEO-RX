import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { useFilters, useResource } from '../hooks/useWorkspace'
import { Filter, Pagination, ResetFilters, ResourceState, Status } from '../components/ui/WorkspaceUI'

export default function InformesPage() {
  const { filters, setFilter, reset } = useFilters({ page: '1', page_size: '20', ordering: '-fecha_creacion' })
  const [revision, setRevision] = useState(0)
  const { data, loading, error } = useResource('/informes/', filters, revision)
  const rows = data?.results || []
  const heading = filters.estado === 'borrador' ? 'Borradores' : filters.estado === 'revisado' ? 'Pendientes de firma' : filters.estado === 'firmado' ? 'Informes validados' : 'Informes'

  return <div className="workspace">
    <header className="page-heading"><div><h1>{heading}</h1><p>Revise, valide y consulte los informes radiológicos generados desde los estudios.</p></div></header>
    <section className="filters" aria-label="Filtros de informes">
      <Filter label="Paciente, CI o contenido" name="search" value={filters.search} onChange={setFilter} placeholder="Buscar informes…" />
      <Filter label="Estado" name="estado" value={filters.estado} onChange={setFilter}>
        <option value="">Todos</option><option value="borrador">Borrador</option><option value="revisado">Revisado</option><option value="firmado">Firmado</option>
      </Filter>
      <Filter label="Creado desde" name="fecha_desde" type="date" value={filters.fecha_desde} onChange={setFilter} />
      <Filter label="Creado hasta" name="fecha_hasta" type="date" value={filters.fecha_hasta} onChange={setFilter} />
      <Filter label="Orden" name="ordering" value={filters.ordering} onChange={setFilter}>
        <option value="-fecha_creacion">Más recientes</option><option value="fecha_creacion">Más antiguos</option><option value="estado">Por estado</option>
      </Filter>
      <ResetFilters onClick={reset} />
    </section>
    <ResourceState loading={loading} error={error} empty={!rows.length} onRetry={() => setRevision(value => value + 1)}>
      <section className="panel">
        <div className="table-scroll"><table className="data-table"><thead><tr>{['Paciente', 'Estudio', 'Creación', 'Médico', 'Estado', 'Acción'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>
          {rows.map(row => {
            const patient = row.paciente || {}
            return <tr key={row.id}>
              <td className="font-semibold text-navy">{`${patient.nombres || ''} ${patient.apellidos || ''}`.trim() || 'Paciente'}<p className="text-xs text-slate-600 font-normal mt-1">CI {patient.ci || '—'}</p></td>
              <td>#{row.estudio}</td>
              <td className="whitespace-nowrap">{row.fecha_creacion ? new Date(row.fecha_creacion).toLocaleDateString('es-BO') : '—'}</td>
              <td>{row.medico_nombre || 'Sin asignar'}</td>
              <td><Status value={row.estado} /></td>
              <td><Link className="btn-secondary whitespace-nowrap" to={`/informes/${row.id}`}>Abrir <ArrowUpRight size={16} /></Link></td>
            </tr>
          })}
        </tbody></table></div>
        <Pagination page={filters.page} pageSize={filters.page_size} total={data?.count || 0} onChange={setFilter} />
      </section>
    </ResourceState>
  </div>
}
