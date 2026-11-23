import { Activity, Layers3, MapPin, ScanSearch } from 'lucide-react'
import { formatModelScore } from '../../utils/modelScore'

const OUTPUT_CONTEXT = {
  Effusion: {
    kind: 'Enfermedad específica',
    evaluates: 'Asociaciones radiográficas aprendidas para derrame pleural, como cambios de densidad y distribución en los espacios pleurales.',
  },
  Atelectasis: {
    kind: 'Enfermedad específica',
    evaluates: 'Asociaciones radiográficas aprendidas para atelectasia, relacionadas con pérdida de volumen u opacidad pulmonar.',
  },
  Pneumothorax: {
    kind: 'Enfermedad específica',
    evaluates: 'Asociaciones radiográficas aprendidas para neumotórax en el campo pulmonar y la periferia torácica.',
  },
  Pneumonia: {
    kind: 'Enfermedad específica',
    evaluates: 'Asociaciones radiográficas aprendidas para neumonía, incluidas distribuciones de opacidad pulmonar.',
  },
  Mass: {
    kind: 'Enfermedad específica',
    evaluates: 'Asociaciones radiográficas aprendidas con masas u opacidades focales de mayor tamaño.',
  },
  Nodule: {
    kind: 'Enfermedad específica',
    evaluates: 'Asociaciones radiográficas aprendidas con nódulos u opacidades focales redondeadas.',
  },
  Pleural_Thickening: {
    kind: 'Enfermedad específica',
    evaluates: 'Asociaciones radiográficas aprendidas con alteraciones del contorno o engrosamiento pleural.',
  },
  Emphysema: {
    kind: 'Enfermedad específica',
    evaluates: 'Asociaciones radiográficas aprendidas con hiperinsuflación y cambios de transparencia pulmonar.',
  },
  Edema: {
    kind: 'Enfermedad específica',
    evaluates: 'Asociaciones radiográficas aprendidas con patrones de edema y distribución bilateral de opacidades.',
  },
  Fibrosis: {
    kind: 'Enfermedad específica',
    evaluates: 'Asociaciones radiográficas aprendidas con cambios intersticiales o reticulares compatibles con fibrosis.',
  },
  CategoryTumoral: {
    kind: 'Categoría amplia',
    evaluates: 'Patrones agrupados de la categoría tumoral, entrenada con masa y nódulo. Esta salida no identifica por sí sola cuál de las dos enfermedades está presente.',
  },
  CategoryPleural: {
    kind: 'Categoría amplia',
    evaluates: 'Patrones agrupados de la categoría pleural: derrame, neumotórax y engrosamiento pleural. No equivale a una enfermedad única.',
  },
  CategoryInfectious: {
    kind: 'Categoría amplia',
    evaluates: 'Patrones agrupados de la categoría infecciosa, entrenada con neumonía y consolidación. No distingue automáticamente entre ambas.',
  },
  CategoryInterstitial: {
    kind: 'Categoría amplia',
    evaluates: 'Patrones agrupados de la categoría intersticial: fibrosis, edema e infiltrado. No confirma una causa específica.',
  },
}

function validScore(value) {
  const score = Number(value)
  return Number.isFinite(score) && score >= 0 && score <= 1 ? score : null
}

function rowsFrom(patologias, hallazgos) {
  if (Array.isArray(hallazgos) && hallazgos.length) {
    return hallazgos
      .map((item) => ({
        key: item.etiqueta_en || item.etiqueta,
        name: item.etiqueta || item.etiqueta_en,
        score: validScore(item.probabilidad_estimada),
        threshold: validScore(item.threshold_usado),
        enabled: item.decision_habilitada !== false,
        detected: item.detectado === true,
        type: item.tipo_salida,
      }))
      .filter((item) => item.name && item.score !== null)
      .sort((a, b) => b.score - a.score)
  }
  return Object.entries(patologias || {})
    .map(([name, value]) => ({ key: null, name, score: validScore(value), threshold: null, enabled: false }))
    .filter((item) => item.score !== null)
    .sort((a, b) => b.score - a.score)
}

function thresholdExplanation(row) {
  if (!row.enabled) return 'Esta salida se conserva para auditoría, pero su decisión está deshabilitada porque no cuenta con una política validada activa.'
  if (row.threshold === null) return 'El resultado no conserva un umbral válido; por eso el puntaje no se convierte en una decisión.'
  const distance = Math.abs(row.score - row.threshold) * 100
  return `${row.score >= row.threshold ? 'Superó' : 'Quedó por debajo de'} su criterio técnico por ${distance.toFixed(1)} puntos (criterio: ${formatModelScore(row.threshold)}).`
}

function ActivationLocation({ row, selected, gradCAM, loading, error, onSelect }) {
  if (!selected) return (
    <button type="button" onClick={() => onSelect?.(row.key)} disabled={!row.key || loading}
      className="mt-3 inline-flex items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-900 transition-colors hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-50">
      <ScanSearch className="h-4 w-4" /> Ver dónde influyó esta salida
    </button>
  )
  if (loading) return <p className="mt-3 text-xs font-semibold text-sky-800">Calculando la localización para esta salida…</p>
  if (error) return <button type="button" onClick={() => onSelect?.(row.key)} className="mt-3 text-xs font-semibold text-rose-700 underline">No se pudo localizar. Reintentar</button>
  const summary = gradCAM?.resumen_activacion
  if (!summary) return <p className="mt-3 text-xs text-slate-500">Seleccionada. Genera el mapa para obtener la distribución espacial.</p>
  return (
    <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50/70 p-3">
      <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-sky-900"><MapPin className="h-3.5 w-3.5" /> Dónde influyó</p>
      <p className="mt-1.5 text-sm leading-6 text-slate-700">{summary.descripcion}</p>
      {summary.disponible && <p className="mt-2 text-xs text-slate-500">Zona de activación más intensa: {summary.cobertura_relativa_pct}% de la imagen. Referencia: {summary.referencia_espacial}.</p>}
    </div>
  )
}

export default function ExplicacionPuntuaciones({
  patologias, hallazgos, gradCAM, gradCAMCargando, gradCAMError,
  patologiaSeleccionada, onPatologiaChange,
}) {
  const rows = rowsFrom(patologias, hallazgos)
  if (!rows.length) return null

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="score-explanation-title">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-navy text-white"><Layers3 className="h-5 w-5" /></div>
        <div>
          <h2 id="score-explanation-title" className="font-heading text-lg font-bold text-navy">Por qué obtuvo cada puntuación</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">Cada salida se explica por separado. El puntaje mide activación del modelo; no es un porcentaje de enfermedad.</p>
        </div>
      </div>

      <div className="mt-5 space-y-4">
        {rows.map((row) => {
          const context = OUTPUT_CONTEXT[row.key] || {
            kind: row.type === 'categoria' ? 'Categoría amplia' : 'Salida específica',
            evaluates: `Asociaciones visuales aprendidas por el modelo para ${row.name.toLowerCase()}.`,
          }
          const selected = patologiaSeleccionada === row.key
          return (
            <article key={row.key || row.name} className={`rounded-xl border p-4 transition-colors ${selected ? 'border-sky-400 bg-sky-50/30' : 'border-slate-200 bg-slate-50/45'}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">{context.kind}</p>
                  <h3 className="mt-1 font-heading text-base font-bold text-navy">{row.name}</h3>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-right">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Puntaje</p>
                  <p className="font-mono text-base font-bold tabular-nums text-navy">{formatModelScore(row.score)}</p>
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg bg-white p-3">
                  <p className="flex items-center gap-2 text-xs font-bold text-navy"><Activity className="h-3.5 w-3.5" /> Por qué quedó en ese nivel</p>
                  <p className="mt-1.5 text-xs leading-5 text-slate-600">{thresholdExplanation(row)}</p>
                </div>
                <div className="rounded-lg bg-white p-3">
                  <p className="text-xs font-bold text-navy">Qué patrón evalúa</p>
                  <p className="mt-1.5 text-xs leading-5 text-slate-600">{context.evaluates}</p>
                </div>
              </div>
              <ActivationLocation row={row} selected={selected} gradCAM={gradCAM}
                loading={gradCAMCargando} error={gradCAMError} onSelect={onPatologiaChange} />
            </article>
          )
        })}
      </div>
      <p className="mt-4 border-t border-slate-200 pt-4 text-xs leading-5 text-slate-500">Grad-CAM muestra influencia espacial aproximada. No demuestra que exista una lesión, no marca sus límites y no reemplaza la lectura médica.</p>
    </section>
  )
}
