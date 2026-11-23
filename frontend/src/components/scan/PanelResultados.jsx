import { motion } from 'framer-motion'
import { Download, ScanLine } from 'lucide-react'
import ListaPatologias from './ListaPatologias'
import VisorImagen from './VisorImagen'
import ExplicacionPuntuaciones from './ExplicacionPuntuaciones'
import Button from '../ui/Button'
import { useAuth } from '../../context/useAuth'
import { useToast } from '../../context/useToast'
import { generarInforme } from '../../api/informes'
import { useEffect, useState } from 'react'

export default function PanelResultados({
  resultado, gradCAM, gradCAMCargando, gradCAMError,
  onPatologiaChange, patologiaSeleccionada,
  estudioId, informeId, onInformeGenerado,
}) {
  const { rol } = useAuth()
  const toast = useToast()
  const [generando, setGenerando] = useState(false)

  const rawPatologias = resultado?.patologias || {}
  const patologias = Array.isArray(rawPatologias?.hallazgos)
    ? Object.fromEntries(rawPatologias.hallazgos.map((item) => [item.etiqueta, Number(item.probabilidad_estimada)]))
    : rawPatologias
  const hallazgos = resultado?.hallazgos || rawPatologias?.hallazgos || []
  const objetivoPrincipal = (resultado?.enfoque || rawPatologias?.enfoque)?.objetivos_gradcam?.[0]?.etiqueta_en
    || hallazgos.find((item) => item?.detectado && item?.etiqueta_en)?.etiqueta_en

  useEffect(() => {
    if (!patologiaSeleccionada && objetivoPrincipal) onPatologiaChange?.(objetivoPrincipal)
  }, [objetivoPrincipal, onPatologiaChange, patologiaSeleccionada])
  const handleGenerarInforme = async () => {
    setGenerando(true)
    try {
      const { data } = await generarInforme(estudioId)
      onInformeGenerado?.(data)
    } catch (e) {
      if (e.response) toast.error(e.response.data?.error || 'No se pudo generar el informe.')
      else toast.red()
    } finally {
      setGenerando(false)
    }
  }

  const handleDescargar = () => {
    const blob = new Blob([JSON.stringify(resultado, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url
    a.download = `resultado_cnn_${resultado.imagen_id || 'neorx'}.json`
    a.click(); URL.revokeObjectURL(url)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <header className="overflow-hidden rounded-2xl border border-sky-200 bg-white shadow-sm">
        <div className="flex items-start gap-4 bg-gradient-to-r from-sky-50 to-white px-5 py-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-navy text-white"><ScanLine className="h-5 w-5" /></div>
          <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-sky-800">Escaneo completado</p><h1 className="mt-1 font-heading text-2xl font-bold text-navy">Resumen del análisis</h1><p className="mt-1 text-sm text-slate-600">Primero se presenta la conclusión; debajo puedes revisar el motivo y la ubicación de cada salida por separado.</p></div>
        </div>
      </header>

      <ListaPatologias
        patologias={patologias}
        hallazgos={hallazgos}
        decision={resultado?.decision || rawPatologias?.decision}
        categoria={resultado?.categoria || rawPatologias?.categoria}
        enfoque={resultado?.enfoque || rawPatologias?.enfoque}
        alcance={resultado?.alcance_modelo || rawPatologias?.alcance || []}
      />

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(360px,.95fr)]">
        <div className="bg-scan-bg rounded-2xl p-5 border border-white/10 lg:sticky lg:top-5">
          <VisorImagen
            imagenUrl={resultado?.imagen_png_url}
            gradCAM={gradCAM}
            gradCAMCargando={gradCAMCargando}
            gradCAMError={gradCAMError}
            esNitida={resultado?.es_nitida}
            varianza={resultado?.varianza_laplaciana}
            patologias={patologias}
            objetivosGradcam={(resultado?.enfoque || rawPatologias?.enfoque)?.objetivos_gradcam}
            patologiaSeleccionada={patologiaSeleccionada}
            onPatologiaChange={onPatologiaChange}
          />
        </div>
        <ExplicacionPuntuaciones
          patologias={patologias}
          hallazgos={hallazgos}
          gradCAM={gradCAM}
          gradCAMCargando={gradCAMCargando}
          gradCAMError={gradCAMError}
          patologiaSeleccionada={patologiaSeleccionada}
          onPatologiaChange={onPatologiaChange}
        />
      </div>

      <div className="flex gap-3">
          {rol === 'medico' && !informeId && (
            <Button variant="primary" loading={generando} onClick={handleGenerarInforme} className="flex-1">
              Generar informe preliminar
            </Button>
          )}
          {rol === 'medico' && informeId && <Button variant="primary" onClick={() => onInformeGenerado?.({id:informeId})}>Abrir informe</Button>}
          <Button variant="secondary" onClick={handleDescargar}>
            <Download className="w-4 h-4" /> JSON
          </Button>
      </div>
    </motion.div>
  )
}
