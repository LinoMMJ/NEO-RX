/**
 * BarraFidelidad — Muestra la confianza diagnóstica del modelo CNN.
 *
 * Consume niveles clínicos centralizados desde /api/diagnostico/niveles-clinicos/
 * Elimina duplicación de umbrales hardcodeados en frontend.
 */
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../../api'

const NIVEL_LABELS = {
  alto: 'ELEVADO',
  moderado: 'MODERADO',
  leve: 'LEVE',
  marginal: 'MARGINAL',
}

function getBarColor(nivel) {
  switch (nivel) {
    case 'alto':      return 'from-danger to-rose-500'
    case 'moderado':  return 'from-orange-400 to-orange-500'
    case 'leve':      return 'from-warning to-amber-400'
    default:          return 'from-slate-400 to-slate-500'
  }
}

function getTextColor(nivel) {
  return {alto: 'text-red-700', moderado: 'text-orange-700', leve: 'text-amber-800', marginal: 'text-slate-600'}[nivel] || 'text-slate-600'
}
function getBgColor(nivel) {
  return {alto: 'bg-red-50', moderado: 'bg-orange-50', leve: 'bg-amber-50', marginal: 'bg-slate-100'}[nivel] || 'bg-slate-100'
}

export default function BarraFidelidad({ patologiaPrincipal, probabilidad, tiempoInferencia }) {
  const [nivelesConfig, setNivelesConfig] = useState(null)

  // Cargar config de niveles (cacheable)
  useEffect(() => {
    api.get('/diagnostico/niveles-clinicos/')
      .then(res => setNivelesConfig(res.data))
      .catch(err => console.warn('[BarraFidelidad] Niveles no cargados, usando fallback:', err))
  }, [])

  if (probabilidad == null) return null
  const pct = Math.round(probabilidad * 100)

  // Clasificar usando backend config o fallback
  const nivel = (() => {
    if (!nivelesConfig) {
      if (probabilidad >= 0.70) return 'alto'
      if (probabilidad >= 0.50) return 'moderado'
      if (probabilidad >= 0.30) return 'leve'
      return 'marginal'
    }
    const { alto, moderado, leve } = nivelesConfig.niveles_generales
    if (probabilidad >= alto) return 'alto'
    if (probabilidad >= moderado) return 'moderado'
    if (probabilidad >= leve) return 'leve'
    return 'marginal'
  })()

  const bar = getBarColor(nivel)
  const textColor = getTextColor(nivel)
  const label = NIVEL_LABELS[nivel]

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="font-heading font-bold text-navy text-base">Confianza diagnóstica</h3>
        <motion.span
          className={`font-mono font-bold text-2xl ${textColor}`}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.4, type: 'spring' }}
        >
          {pct}%
        </motion.span>
      </div>

      {/* Barra principal con umbral */}
      <div className="relative">
        <div className="w-full h-6 bg-slate-100 rounded-full overflow-hidden">
          <motion.div
            className={`h-full rounded-full bg-gradient-to-r ${bar}`}
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 1.2, ease: 'easeOut', delay: 0.2 }}
          />
        </div>
        {/* Líneas de umbral desde config */}
        <div className="absolute top-0 bottom-0 flex flex-col items-center" style={{ left: `${nivelesConfig?.niveles_generales?.leve ? (nivelesConfig.niveles_generales.leve * 100) : 30}%` }}>
          <div className="w-0.5 h-6 bg-slate-400/60" />
        </div>
        <div className="absolute top-7 text-[10px] font-mono text-slate-400" style={{ left: `${nivelesConfig?.niveles_generales?.leve ? (nivelesConfig.niveles_generales.leve * 100) : 30}%` }}>
          umbral {Math.round((nivelesConfig?.niveles_generales?.leve || 0.30) * 100)}%
        </div>
        <div className="absolute top-0 bottom-0 flex flex-col items-center" style={{ left: `${nivelesConfig?.niveles_generales?.moderado ? (nivelesConfig.niveles_generales.moderado * 100) : 50}%` }}>
          <div className="w-0.5 h-6 bg-slate-400/60" />
        </div>
        <div className="absolute top-7 text-[10px] font-mono text-slate-400" style={{ left: `${nivelesConfig?.niveles_generales?.moderado ? (nivelesConfig.niveles_generales.moderado * 100) : 50}%` }}>
          umbral {Math.round((nivelesConfig?.niveles_generales?.moderado || 0.50) * 100)}%
        </div>
      </div>

      <div className="mt-8">
        <p className="font-body text-sm text-slate-600">
          Hallazgo principal:{' '}
          <span className={`font-heading font-bold ${textColor}`}>{patologiaPrincipal}</span>
          {' '}
          <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${getBgColor(nivel)}`}>{label}</span>
        </p>
      </div>

      <p className="mt-3 font-body text-xs text-slate-400 leading-relaxed border-t border-slate-100 pt-3">
        La confianza representa la probabilidad posterior calibrada del modelo ResNet-50
        para el hallazgo de mayor relevancia. Umbrales desde configuración centralizada.
        {tiempoInferencia && (
          <span className="font-mono"> · Inferencia: {tiempoInferencia}s</span>
        )}
      </p>
    </div>
  )
}
