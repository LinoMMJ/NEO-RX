import { useState } from 'react'
import { motion } from 'framer-motion'
import { ShieldCheck } from 'lucide-react'

// Descripciones clínicas para tooltip hover
const DESCRIPCIONES = {
  // Infecciones e inflamación pulmonar
  'Neumonía':              { en: 'Pneumonia',          desc: 'Infección bacteriana o viral del parénquima pulmonar con exudado alveolar' },
  'Consolidación':         { en: 'Consolidation',      desc: 'Ocupación alveolar por exudado inflamatorio, pus o fluido' },
  'Infiltrado pulmonar':   { en: 'Infiltration',       desc: 'Opacidad heterogénea de límites difusos; puede indicar infección o inflamación' },
  // Opacidades y lesiones parenquimatosas
  'Opacidad pulmonar':     { en: 'Lung Opacity',       desc: 'Aumento generalizado de densidad del parénquima pulmonar' },
  'Lesión pulmonar':       { en: 'Lung Lesion',        desc: 'Área focal de alteración parenquimatosa; incluye abscesos, TB y lesiones post-infecciosas' },
  // Patología pleural
  'Derrame pleural':       { en: 'Effusion',           desc: 'Acumulación de líquido en el espacio pleural' },
  'Neumotórax':            { en: 'Pneumothorax',       desc: 'Presencia de aire libre en el espacio pleural con colapso pulmonar' },
  'Engrosamiento pleural': { en: 'Pleural_Thickening', desc: 'Engrosamiento fibrótico de la pleura, frecuente tras infecciones o exposición a asbesto' },
  // Patología obstructiva e intersticial
  'Atelectasia':           { en: 'Atelectasis',        desc: 'Colapso o pérdida de volumen pulmonar por obstrucción o compresión' },
  'Enfisema':              { en: 'Emphysema',          desc: 'Destrucción de los tabiques alveolares con hiperinsuflación; EPOC' },
  'Fibrosis pulmonar':     { en: 'Fibrosis',           desc: 'Proliferación de tejido fibroso que reemplaza el parénquima sano' },
  'Edema pulmonar':        { en: 'Edema',              desc: 'Acumulación de líquido en el intersticio y alvéolos; falla cardíaca o SDRA' },
  // Lesiones focales (oncológico / TB)
  'Nódulo pulmonar':       { en: 'Nodule',             desc: 'Opacidad redondeada < 3 cm; puede ser benigna (granuloma) o maligna' },
  'Masa pulmonar':         { en: 'Mass',               desc: 'Opacidad redondeada ≥ 3 cm; alta sospecha de neoplasia primaria o metástasis' },
}

function getBadge(prob) {
  if (prob >= 0.70) return { label: 'CRÍTICO',  cls: 'bg-danger/15 text-danger border-danger/30' }
  if (prob >= 0.40) return { label: 'MODERADO', cls: 'bg-orange-500/15 text-orange-500 border-orange-500/30' }
  if (prob >= 0.20) return { label: 'LEVE',     cls: 'bg-warning/15 text-warning border-warning/30' }
  return               { label: 'MARGINAL', cls: 'bg-slate-500/15 text-slate-500 border-slate-500/30' }
}

function getBarColor(prob) {
  if (prob >= 0.70) return 'from-danger to-rose-400'
  if (prob >= 0.40) return 'from-orange-400 to-orange-500'
  if (prob >= 0.20) return 'from-warning to-amber-400'
  return 'from-slate-400 to-slate-500'
}

export default function ListaPatologias({ patologias }) {
  const [tooltip, setTooltip] = useState(null)

  // Solo mostrar > 5%
  const lista = patologias ? Object.entries(patologias).filter(([, p]) => p >= 0.05) : []

  // Estado vacío: sin datos o sin hallazgos significativos
  if (lista.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h3 className="font-heading font-bold text-navy text-base mb-4">Hallazgos detectados</h3>
        <div className="flex flex-col items-center justify-center py-8 text-center gap-2">
          <div className="w-12 h-12 rounded-full bg-success/10 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6 text-success" />
          </div>
          <p className="font-heading font-semibold text-navy text-sm">No se detectaron hallazgos</p>
          <p className="font-body text-xs text-slate-400 max-w-xs">
            El modelo no identificó patologías por encima del umbral de mención (5%).
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 className="font-heading font-bold text-navy text-base mb-4">Hallazgos detectados</h3>

      <div className="space-y-3">
        {lista.map(([nombre, prob], i) => {
          const pct = Math.round(prob * 100)
          const badge = getBadge(prob)
          const bar = getBarColor(prob)
          const info = DESCRIPCIONES[nombre]

          return (
            <motion.div
              key={nombre}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.06 }}
              className="relative"
              onMouseEnter={() => setTooltip(nombre)}
              onMouseLeave={() => setTooltip(null)}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="font-body text-sm font-semibold text-navy flex-1">{nombre}</span>
                <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border ${badge.cls} ${prob >= 0.70 ? 'animate-pulse' : ''}`}>
                  {badge.label}
                </span>
                <span className="font-mono text-sm font-bold text-slate-700 w-12 text-right">{pct}%</span>
              </div>
              <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                <motion.div
                  className={`h-full rounded-full bg-gradient-to-r ${bar}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 + i * 0.06 }}
                />
              </div>

              {/* Tooltip */}
              {tooltip === nombre && info && (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="absolute z-10 left-0 top-full mt-1 bg-navy text-white text-xs font-body px-3 py-2 rounded-lg shadow-xl max-w-xs"
                >
                  <span className="font-mono text-teal-med">{info.en}</span>
                  <p className="mt-0.5 text-white/80">{info.desc}</p>
                </motion.div>
              )}
            </motion.div>
          )
        })}
      </div>

      <p className="font-body text-xs text-slate-400 mt-4 border-t border-slate-100 pt-3">
        Pasa el cursor sobre cada hallazgo para ver la descripción clínica.
        Ordenados por probabilidad descendente.
      </p>
    </div>
  )
}
