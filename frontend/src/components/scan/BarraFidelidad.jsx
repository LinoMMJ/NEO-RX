/**
 * BarraFidelidad — Muestra la confianza diagnóstica del modelo CNN.
 *
 * El valor proviene directamente de la salida del modelo ResNet-50:
 * una probabilidad posterior calibrada en [0,1] para la patología de mayor
 * relevancia. NO es un threshold de imagen; es la salida de la red neuronal.
 *
 * Umbral operativo 50% = op_threshs del modelo torchxrayvision (valor
 * determinado durante la fase de calibración sobre los datasets de prueba).
 */
import { motion } from 'framer-motion'

// Color según nivel de confianza
function getColor(prob) {
  if (prob < 0.30) return { bar: 'from-slate-400 to-slate-500',   text: 'text-slate-400', label: 'MARGINAL' }
  if (prob < 0.50) return { bar: 'from-warning to-amber-400',     text: 'text-warning',   label: 'LEVE' }
  if (prob < 0.70) return { bar: 'from-orange-400 to-orange-500', text: 'text-orange-400',label: 'MODERADO' }
  return              { bar: 'from-danger to-rose-500',           text: 'text-danger',    label: 'ELEVADO' }
}

export default function BarraFidelidad({ patologiaPrincipal, probabilidad, tiempoInferencia }) {
  if (probabilidad == null) return null
  const pct = Math.round(probabilidad * 100)
  const { bar, text, label } = getColor(probabilidad)

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="font-heading font-bold text-navy text-base">Confianza diagnóstica</h3>
        <motion.span
          className={`font-mono font-bold text-2xl ${text}`}
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
        {/* Línea de umbral operativo (50%) */}
        <div className="absolute top-0 bottom-0 flex flex-col items-center" style={{ left: '50%' }}>
          <div className="w-0.5 h-6 bg-slate-400/60" />
        </div>
        <div className="absolute top-7 text-[10px] font-mono text-slate-400" style={{ left: 'calc(50% - 28px)' }}>
          umbral 50%
        </div>
      </div>

      <div className="mt-8">
        <p className="font-body text-sm text-slate-600">
          Hallazgo principal:{' '}
          <span className={`font-heading font-bold ${text}`}>{patologiaPrincipal}</span>
          {' '}
          <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${text} bg-current/10`}>{label}</span>
        </p>
      </div>

      <p className="mt-3 font-body text-xs text-slate-400 leading-relaxed border-t border-slate-100 pt-3">
        La confianza representa la probabilidad posterior calibrada del modelo ResNet-50
        para el hallazgo de mayor relevancia. Umbral operativo: 50% (op_threshs del modelo).
        {tiempoInferencia && (
          <span className="font-mono"> · Inferencia: {tiempoInferencia}s</span>
        )}
      </p>
    </div>
  )
}
