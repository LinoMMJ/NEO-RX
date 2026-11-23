import { formatModelScore } from '../../utils/modelScore'
import { partitionFindings } from '../../utils/modelFindings'

const DECISION_STYLES = {
  hallazgo_detectado: 'border-amber-300 bg-amber-50 text-amber-950',
  hallazgos_coexistentes: 'border-orange-300 bg-orange-50 text-orange-950',
  indeterminado: 'border-slate-300 bg-slate-50 text-slate-800',
  modelo_pendiente_validacion: 'border-sky-300 bg-sky-50 text-sky-950',
  categoria_detectada: 'border-teal-med/40 bg-teal-med/10 text-navy',
  categoria_ambigua: 'border-orange-300 bg-orange-50 text-orange-950',
}

function TechnicalRow({ row }) {
  return (
    <li className="rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="min-w-0 text-sm font-semibold text-navy">{row.name}</span>
        <span className="font-mono text-sm tabular-nums text-slate-700" aria-label={`Puntuación técnica de ${row.name}`}>
          {formatModelScore(row.score)}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {!row.enabled
          ? 'Decisión deshabilitada: falta evidencia de validación suficiente.'
          : row.threshold === null
            ? 'Umbral no conservado en este resultado.'
            : `${row.above ? 'Alcanzó' : 'No alcanzó'} el criterio técnico configurado.`}
      </p>
    </li>
  )
}

function categoryModelScore(categoria) {
  const raw = categoria?.puntuacion_modelo ?? categoria?.puntuacion_tecnica ?? categoria?.puntuacion
  const score = Number(raw)
  return Number.isFinite(score) && score >= 0 && score <= 1 ? score : null
}

function PrioritizedResult({ enfoque, decision, categoria }) {
  const primary = enfoque.estado === 'hallazgos_prioritarios'
  const categoryScore = categoryModelScore(categoria)
  return <section className="rounded-xl border border-slate-200 bg-white p-5" aria-label="Análisis prioritario y orientación por categorías">
    <h3 className="font-heading text-base font-bold text-navy">Conclusión asistida</h3>
    <div role="status" className="mt-3 text-sm leading-relaxed text-slate-700">
      <p className="font-semibold text-navy">{decision?.titulo || 'Resultado no concluyente'}</p>
      <p className="mt-2">{decision?.mensaje}</p>
    </div>
    {primary && <ul className="mt-4 space-y-3" aria-label="Hallazgos prioritarios detectados">
      {enfoque.hallazgos_detectados.map(row => <li key={row.etiqueta_en} className="flex flex-wrap justify-between gap-2 border-b border-slate-200 py-2 text-sm">
        <span className="font-semibold">{row.etiqueta}</span>
        <span>Puntuación: {formatModelScore(row.probabilidad_estimada)}</span>
      </li>)}
    </ul>}
    {!primary && categoria?.estado === 'seleccionada' && <div className="mt-4 rounded-xl border border-teal-med/30 bg-teal-med/5 p-3" aria-label="Categoría orientativa">
      <p className="text-lg font-semibold text-navy">{categoria.nombre}</p>
      {categoryScore !== null && <p className="mt-1 text-sm text-slate-700" aria-label={`Puntuación del modelo para categoría ${categoria.nombre}`}>
        Puntuación del modelo: <span className="font-mono font-semibold tabular-nums">{formatModelScore(categoryScore)}</span>
      </p>}
    </div>}
    <p className="mt-4 text-sm leading-relaxed text-slate-600">
      Primero se evalúa derrame pleural. Si no alcanza el criterio, se consulta una sola orientación por categorías.
      {' '}Las puntuaciones no son porcentajes de certeza diagnóstica.
    </p>
  </section>
}

export default function ListaPatologias({ patologias, hallazgos = [], decision = null, categoria = null, alcance = [], enfoque = null }) {
  if (enfoque) return <PrioritizedResult enfoque={enfoque} decision={decision} categoria={categoria} />
  const { rows, candidates } = partitionFindings(patologias, hallazgos)
  const known = rows.some((row) => row.threshold !== null)
  const categoryStatus = categoria?.estado ? categoria : {
    estado: 'no_concluyente',
    nombre: 'No concluyente',
    mensaje: 'Este resultado se generó antes de incorporar la clasificación por categorías. Debe reprocesarse con un checkpoint categorial validado.',
  }
  const categoryScore = categoryModelScore(categoryStatus)
  const effectiveDecision = decision?.estado ? decision : (
    !rows.length
      ? { estado: 'indeterminado', titulo: 'Sin resultado disponible', mensaje: 'No existen puntuaciones técnicas para interpretar.' }
      : !known
        ? { estado: 'modelo_pendiente_validacion', titulo: 'Resultado histórico no interpretable', mensaje: 'No conserva los umbrales ni la política de decisión usados al adquirirlo.' }
        : !candidates.length
          ? { estado: 'indeterminado', titulo: 'Sin evidencia suficiente', mensaje: 'Ninguna señal alcanzó su criterio. Esto no descarta enfermedad.' }
          : candidates.length === 1
            ? { estado: 'hallazgo_detectado', titulo: `Hallazgo compatible con ${candidates[0].name.toLowerCase()}`, mensaje: 'Requiere confirmación profesional sobre la radiografía.' }
            : { estado: 'hallazgos_coexistentes', titulo: 'Más de un hallazgo requiere revisión', mensaje: 'Pueden coexistir; el sistema no fuerza un diagnóstico único.' }
  )

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="Interpretación de la salida CNN">
      <h3 className="font-heading text-base font-bold text-navy">Conclusión asistida</h3>
      <div className={`mt-3 rounded-xl border p-4 ${DECISION_STYLES[effectiveDecision.estado] || DECISION_STYLES.indeterminado}`} role="status">
        <p className="font-heading text-sm font-bold">{effectiveDecision.titulo}</p>
        <p className="mt-1 text-xs leading-relaxed">{effectiveDecision.mensaje}</p>
      </div>

      {categoryStatus.estado === 'seleccionada' && (
        <div className="mt-4 rounded-xl border border-teal-med/25 bg-teal-med/5 p-4" aria-label="Categoría principal">
          <p className="text-xs font-semibold uppercase tracking-wide text-teal-dark">Categoría seleccionada</p>
          <p className="mt-1 font-heading text-lg font-bold text-navy">{categoryStatus.nombre}</p>
          {categoryScore !== null && <p className="mt-1 text-sm text-slate-700" aria-label={`Puntuación del modelo para categoría ${categoryStatus.nombre}`}>
            Puntuación del modelo: <span className="font-mono font-semibold tabular-nums">{formatModelScore(categoryScore)}</span>
          </p>}
          <p className="mt-1 text-xs leading-relaxed text-slate-600">
            Se muestran únicamente las señales incluidas en esta categoría.
          </p>
          <ul className="mt-3 space-y-2" aria-label={`Señales de la categoría ${categoryStatus.nombre}`}>
            {(categoryStatus.enfermedades || []).map((item) => (
              <li key={item.etiqueta_en || item.etiqueta} className="flex items-center justify-between gap-3 rounded-lg bg-white px-3 py-2 text-sm">
                <span className="font-semibold text-navy">{item.etiqueta}</span>
                <span className="font-mono tabular-nums text-slate-700">{formatModelScore(item.probabilidad_estimada)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-slate-500">
            Son puntuaciones del modelo, no porcentajes de certeza diagnóstica.
          </p>
        </div>
      )}

      {categoryStatus.estado !== 'seleccionada' && (
        <div className="mt-4 rounded-xl border border-slate-300 bg-slate-50 p-4" aria-label="Clasificación por categorías">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Clasificación por categorías</p>
          <p className="mt-1 font-heading text-lg font-bold text-navy">No concluyente</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-600">{categoryStatus.mensaje}</p>
          <p className="mt-3 text-xs text-slate-500">No se muestran enfermedades de categorías competidoras.</p>
        </div>
      )}

      {Array.isArray(effectiveDecision.hallazgos_principales) && effectiveDecision.hallazgos_principales.length > 0 && (
        <ul className="mt-4 space-y-2" aria-label="Hallazgos que requieren revisión">
          {effectiveDecision.hallazgos_principales.map((name) => (
            <li key={name} className="rounded-lg border border-teal-med/25 bg-teal-med/5 px-3 py-2 text-sm font-semibold text-navy">
              {name}
            </li>
          ))}
        </ul>
      )}

      {alcance.length > 0 && (
        <p className="mt-4 text-xs text-slate-500">El modelo evalúa únicamente: {alcance.join(', ')}.</p>
      )}

      {rows.length > 0 && (
        <details className="mt-4 border-t border-slate-200 pt-3">
          <summary className="cursor-pointer text-sm font-semibold text-navy">Ver salida técnica para auditoría</summary>
          <p className="my-3 text-xs leading-relaxed text-slate-500">
            Estas activaciones y umbrales no son porcentajes de enfermedad ni sustituyen la interpretación médica.
          </p>
          <ul className="space-y-2" aria-label="Salida técnica del modelo">
            {rows.map((row) => <TechnicalRow key={row.name} row={row} />)}
          </ul>
        </details>
      )}
    </section>
  )
}
