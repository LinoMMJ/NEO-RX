import { motion } from 'framer-motion'
import { Brain, Download } from 'lucide-react'
import ListaPatologias from './ListaPatologias'
import VisorImagen from './VisorImagen'
import Button from '../ui/Button'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { generarInforme } from '../../api/informes'
import { useState } from 'react'

export default function PanelResultados({
  resultado, gradCAM, gradCAMCargando, gradCAMError,
  onPatologiaChange, patologiaSeleccionada,
  estudioId, onInformeGenerado,
}) {
  const { rol } = useAuth()
  const toast = useToast()
  const [generando, setGenerando] = useState(false)

  const patologias = resultado?.patologias || {}

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
      className="grid grid-cols-1 lg:grid-cols-2 gap-6"
    >
      {/* Panel izquierdo — Visor imagen */}
      <div className="bg-scan-bg rounded-2xl p-5 border border-white/10">
        <VisorImagen
          imagenUrl={resultado?.imagen_png_url}
          gradCAM={gradCAM}
          gradCAMCargando={gradCAMCargando}
          gradCAMError={gradCAMError}
          esNitida={resultado?.es_nitida}
          varianza={resultado?.varianza_laplaciana}
          patologias={patologias}
          patologiaSeleccionada={patologiaSeleccionada}
          onPatologiaChange={onPatologiaChange}
        />
      </div>

      {/* Panel derecho — Datos CNN */}
      <div className="flex flex-col gap-4">
        {/* Lista de patologías */}
        <ListaPatologias patologias={patologias} />

        {/* Sobre este análisis */}
        <div className="bg-teal-med/5 border border-teal-med/20 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-teal-med" />
            <h4 className="font-heading font-bold text-navy text-sm">Análisis por Red Neuronal Convolucional</h4>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-body text-xs text-slate-600">
            <span className="text-slate-400">Arquitectura</span><span className="font-semibold">ResNet-50 (50 capas residuales)</span>
            <span className="text-slate-400">Parámetros</span><span className="font-mono">25.5M</span>
            <span className="text-slate-400">Tiempo inferencia</span><span className="font-mono">{resultado?.tiempo_inferencia_seg}s</span>
            <span className="text-slate-400">Resolución</span><span className="font-mono">512×512 px</span>
            <span className="text-slate-400">Radiografías entrenamiento</span><span className="font-mono">&gt;112,000</span>
            <span className="text-slate-400">Datasets</span><span>PadChest · NIH · RSNA · SIIM · VinBigData</span>
            <span className="text-slate-400">Visualización</span><span>Grad-CAM (layer4)</span>
          </div>
          <p className="mt-3 font-body text-xs text-slate-500 italic border-t border-teal-med/10 pt-2">
            El mapa de calor muestra los gradientes de la clase predicha respecto a los feature maps
            de la capa convolucional final (layer4), evidenciando las regiones anatómicas que
            determinaron el diagnóstico.
          </p>
        </div>

        {/* Acciones */}
        <div className="flex gap-3">
          {rol === 'medico' && (
            <Button variant="primary" loading={generando} onClick={handleGenerarInforme} className="flex-1">
              Generar informe preliminar
            </Button>
          )}
          <Button variant="secondary" onClick={handleDescargar}>
            <Download className="w-4 h-4" /> JSON
          </Button>
        </div>
      </div>
    </motion.div>
  )
}
