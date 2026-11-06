import { motion } from 'framer-motion'
import { Download } from 'lucide-react'
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
          objetivosGradcam={(resultado?.enfoque || rawPatologias?.enfoque)?.objetivos_gradcam}
          patologiaSeleccionada={patologiaSeleccionada}
          onPatologiaChange={onPatologiaChange}
        />
      </div>

      {/* Panel derecho — Datos CNN */}
      <div className="flex flex-col gap-4">
        {/* Lista de patologías */}
        <ListaPatologias
          patologias={patologias}
          hallazgos={resultado?.hallazgos || rawPatologias?.hallazgos || []}
          decision={resultado?.decision || rawPatologias?.decision}
          categoria={resultado?.categoria || rawPatologias?.categoria}
          enfoque={resultado?.enfoque || rawPatologias?.enfoque}
          alcance={resultado?.alcance_modelo || rawPatologias?.alcance || []}
        />
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
