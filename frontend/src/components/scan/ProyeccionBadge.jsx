import { motion } from 'framer-motion'
import { ScanLine, FileText, Sparkles } from 'lucide-react'

const ESTILOS = {
  PA:  { cls: 'bg-blue-500/10 text-blue-600 border-blue-500/30', label: 'Proyección PA · Postero-Anterior' },
  AP:  { cls: 'bg-orange-500/10 text-orange-600 border-orange-500/30', label: 'Proyección AP · Antero-Posterior (portátil)' },
  LAT: { cls: 'bg-purple-500/10 text-purple-600 border-purple-500/30', label: 'Proyección Lateral' },
}

/**
 * ProyeccionBadge — Campo informativo de SOLO LECTURA del tipo de proyección.
 * Antes del upload: estado "por detectar". Después: badge según el resultado
 * de detect_projection_type del backend, con indicador de la fuente.
 */
export default function ProyeccionBadge({ proyeccion }) {
  if (!proyeccion?.tipo) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-100 border border-slate-200">
        <ScanLine className="w-4 h-4 text-slate-400" />
        <span className="font-body text-sm text-slate-500">Tipo: Por detectar (automático)</span>
      </div>
    )
  }

  const { tipo, fuente } = proyeccion
  const estilo = ESTILOS[tipo] || ESTILOS.PA
  const esDicom = fuente === 'dicom_tag'

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex flex-col gap-1.5"
    >
      <span className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border font-body text-sm font-semibold w-fit ${estilo.cls}`}>
        <ScanLine className="w-4 h-4" />
        {estilo.label}
      </span>
      <span className="inline-flex items-center gap-1.5 font-body text-[11px] text-slate-400 pl-1">
        {esDicom
          ? <><FileText className="w-3 h-3" /> Detectado del archivo DICOM</>
          : <><Sparkles className="w-3 h-3" /> Inferido por análisis</>}
      </span>
    </motion.div>
  )
}
