import { formatModelScore } from '../../utils/modelScore'
import { partitionFindings } from '../../utils/modelFindings'

function FindingRow({ row }) {
  return (
    <li className="rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-sm font-semibold text-navy">{row.name}</span>
        <span className="font-mono text-sm text-slate-700" aria-label={`Puntuación de ${row.name}`}>{formatModelScore(row.score)}</span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {row.threshold === null ? 'Umbral no conservado en este resultado.'
          : `${row.above ? 'Supera' : 'No supera'} el umbral ${formatModelScore(row.threshold)}.`}
      </p>
    </li>
  )
}

export default function ListaPatologias({ patologias, hallazgos = [] }) {
  const { rows, candidates, other } = partitionFindings(patologias, hallazgos)
  const known = rows.some((row) => row.threshold !== null)
  return (
    <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm" aria-label="Interpretación de la salida CNN">
      <h3 className="font-heading font-bold text-navy text-base">Señales para revisión</h3>
      <p className="mt-2 mb-4 text-xs leading-relaxed text-slate-500">
        Puntuaciones de activación sobre 100; no son porcentajes de certeza ni diagnósticos confirmados.
        Se destacan solo las clases que superan su umbral de validación.
      </p>
      {!rows.length ? (
        <p className="text-sm text-slate-600">No hay puntuaciones disponibles. La ausencia de resultados no permite descartar patologías.</p>
      ) : !known ? (
        <p className="text-sm text-slate-600">Resultado histórico sin umbrales conservados. No se puede determinar qué señales superaron el criterio del modelo.</p>
      ) : !candidates.length ? (
        <p className="text-sm text-slate-600">Ninguna señal supera su umbral. Esto no descarta enfermedad.</p>
      ) : (
        <>
          <p className="mb-3 text-sm font-semibold text-navy">{candidates.length === 1 ? '1 señal supera su umbral' : `${candidates.length} señales superan sus umbrales`}</p>
          {candidates.length > 1 && <p role="note" className="mb-3 rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-navy">
            Resultado con múltiples señales: no permite escoger un diagnóstico único. Pueden coexistir hallazgos o existir falsos positivos; requiere revisión de la imagen.
          </p>}
          <ul className="space-y-2" aria-label="Señales sobre umbral">{candidates.map((row) => <FindingRow key={row.name} row={row} />)}</ul>
        </>
      )}
      {other.length > 0 && (
        <details className="mt-4 border-t border-slate-200 pt-3">
          <summary className="cursor-pointer text-sm font-semibold text-navy">Ver otras puntuaciones ({other.length})</summary>
          <p className="my-3 text-xs text-slate-500">Valores técnicos bajo umbral o sin umbral registrado; no son diagnósticos adicionales.</p>
          <ul className="space-y-2" aria-label="Otras puntuaciones">{other.map((row) => <FindingRow key={row.name} row={row} />)}</ul>
        </details>
      )}
    </section>
  )
}
