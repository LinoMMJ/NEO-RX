import { motion } from 'framer-motion'
import { Brain, Download } from 'lucide-react'
import ListaPatologias from './ListaPatologias'
import VisorImagen from './VisorImagen'
import Button from '../ui/Button'
import { useAuth } from '../../context/useAuth'
import { useToast } from '../../context/useToast'
import { generarInforme } from '../../api/informes'
import { useState } from 'react'

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
  const modelName = resultado?.modelo || rawPatologias?.modelo || 'Modelo CNN'
  const denseNet = modelName.toLowerCase().includes('densenet')
  const modelLabel = denseNet ? 'DenseNet-121' : modelName.toLowerCase().includes('resnet') ? 'ResNet-50' : modelName
  const modelParams = denseNet ? '≈8.0 M' : modelName.toLowerCase().includes('resnet') ? '≈25.5 M' : '—'
  const inputResolution = resultado?.resolucion_entrada

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
        <ListaPatologias patologias={patologias} hallazgos={resultado?.hallazgos || rawPatologias?.hallazgos || []} />
        {resultado?.advertencias_modelo?.map((message) => <p key={message} role="alert" className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm text-navy">{message}</p>)}

        {/* Sobre este análisis */}
        <div className="bg-teal-med/5 border border-teal-med/20 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-teal-med" />
            <h4 className="font-heading font-bold text-navy text-sm">Análisis por Red Neuronal Convolucional</h4>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-body text-xs text-slate-600">
            <span className="text-slate-400">Arquitectura</span><span className="font-semibold">{modelLabel}</span>
            <span className="text-slate-400">Parámetros</span><span className="font-mono">{modelParams}</span>
            <span className="text-slate-400">Tiempo inferencia</span><span className="font-mono">{resultado?.tiempo_inferencia_seg}s</span>
            <span className="text-slate-400">Resolución</span><span className="font-mono">{inputResolution ? `${inputResolution}×${inputResolution} px` : 'No registrada'}</span>
            <span className="text-slate-400">Tipo de modelo</span><span className="font-mono">{resultado?.es_fine_tuned ? 'Ajustado con NIH' : 'Baseline preentrenado'}</span>
            <span className="text-slate-400">Pesos</span><span className="break-all">{modelName}</span>
            <span className="text-slate-400">Visualización</span><span>Grad-CAM</span>
          </div>
          <p className="mt-3 font-body text-xs text-slate-500 italic border-t border-teal-med/10 pt-2">
            El mapa de calor señala las regiones que más influyeron en la puntuación del modelo.
            Es una ayuda visual experimental y requiere interpretación por un profesional médico.
          </p>
        </div>

        {/* Acciones */}
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
      </div>
    </motion.div>
  )
}
