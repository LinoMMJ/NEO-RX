import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, AlertTriangle } from 'lucide-react'
import Spinner from '../ui/Spinner'
import usePrivateImage from '../../hooks/usePrivateImage'

// Placeholder vectorial cuando la imagen no está disponible o falla la carga
function PlaceholderRadiografia() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 text-center py-8">
      <svg viewBox="0 0 200 200" className="w-32 h-32" aria-hidden="true">
        <ellipse cx="70" cy="100" rx="40" ry="60" fill="none" stroke="#1e3a5f" strokeWidth="2" />
        <ellipse cx="130" cy="100" rx="40" ry="60" fill="none" stroke="#1e3a5f" strokeWidth="2" />
        <line x1="100" y1="40" x2="100" y2="160" stroke="#1e3a5f" strokeWidth="1" />
      </svg>
      <p className="font-body text-sm text-white/40">Imagen no disponible</p>
    </div>
  )
}

// Mapa español → inglés para los pills de selección de patología (Grad-CAM)
const PATOLOGIAS_EN = {
  'Neumonía':             'Pneumonia',
  'Consolidación':        'Consolidation',
  'Infiltrado pulmonar':  'Infiltration',
  'Opacidad pulmonar':    'Lung Opacity',
  'Lesión pulmonar':      'Lung Lesion',
  'Derrame pleural':      'Effusion',
  'Neumotórax':           'Pneumothorax',
  'Engrosamiento pleural':'Pleural_Thickening',
  'Atelectasia':          'Atelectasis',
  'Enfisema':             'Emphysema',
  'Fibrosis pulmonar':    'Fibrosis',
  'Edema pulmonar':       'Edema',
  'Nódulo pulmonar':      'Nodule',
  'Masa pulmonar':        'Mass',
}

const VISTAS = [
  { id: 'original',  label: 'Original' },
  { id: 'overlay',   label: 'Superposición CNN' },
  { id: 'calor',     label: 'Solo mapa de calor' },
]

export default function VisorImagen({
  imagenUrl, gradCAM, gradCAMCargando, gradCAMError, esNitida, varianza,
  patologias, patologiaSeleccionada, onPatologiaChange,
}) {
  const [vista, setVista] = useState('original')
  const [failedSource, setFailedSource] = useState(null)

  // Mientras GradCAM carga, muestra imagen original como fondo (nunca placeholder vacío)
  const imgSrc =
    vista === 'overlay' ? (gradCAM?.overlay || imagenUrl) :
    vista === 'calor'   ? (gradCAM?.solo_calor || imagenUrl) :
    imagenUrl

  const privateSrc = usePrivateImage(imgSrc)

  // Grad-CAM no disponible: pedimos overlay/calor pero solo hay imagen base
  const gradcamNoDisponible =
    vista !== 'original' && !gradCAMCargando && (gradCAMError || !gradCAM)

  // Solo muestra placeholder si realmente no hay ninguna URL de imagen
  const mostrarPlaceholder = !privateSrc || failedSource === privateSrc

  // Patologías con prob > 40% para mostrar como pills
  const patologiasSignificativas = patologias
    ? Object.entries(patologias).filter(([, p]) => p > 0.4)
    : []

  return (
    <div className="flex flex-col h-full">
      {/* Toggle de vista */}
      <div className="flex gap-1 p-1 bg-surface/50 rounded-xl mb-3">
        {VISTAS.map((v) => (
          <button
            key={v.id}
            onClick={() => setVista(v.id)}
            disabled={v.id !== 'original' && !gradCAM && !gradCAMCargando}
            className={`
              flex-1 py-1.5 px-2 rounded-lg text-xs font-heading font-semibold
              transition-all duration-200 cursor-pointer
              ${vista === v.id
                ? 'bg-teal-med text-white shadow-sm'
                : 'text-white/50 hover:text-white/80 disabled:opacity-30 disabled:cursor-not-allowed'
              }
            `}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* Imagen */}
      <div className="relative rounded-xl overflow-hidden bg-scan-bg border border-white/10 flex-1 flex items-center justify-center min-h-[360px]">
        {mostrarPlaceholder ? (
          <PlaceholderRadiografia />
        ) : (
          <AnimatePresence mode="wait">
            <motion.img
              key={imgSrc}
              src={privateSrc}
              alt="Radiografía de tórax"
              onError={() => setFailedSource(privateSrc)}
              className="w-full h-full object-contain max-h-[420px]"
              style={{ filter: vista === 'original' ? 'brightness(1.1) contrast(1.05)' : 'none' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
            />
          </AnimatePresence>
        )}

        {/* Spinner mientras se calcula Grad-CAM (puede tardar ~15s en CPU) */}
        {gradCAMCargando && vista !== 'original' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-scan-bg/75">
            <Spinner size="xl" color="teal" />
            <p className="font-mono text-xs text-teal-med/80 animate-pulse">
              Calculando mapa de calor…
            </p>
          </div>
        )}

        {/* Grad-CAM no disponible → se muestra imagen original + aviso */}
        {gradcamNoDisponible && !mostrarPlaceholder && (
          <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono font-semibold
            bg-warning/20 text-warning border border-warning/30 max-w-[85%]">
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
            Mapa de calor no disponible — mostrando imagen original
          </div>
        )}

        {/* Badge de nitidez */}
        {varianza != null && (
          <div className={`absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono font-semibold
            ${esNitida
              ? 'bg-success/20 text-success border border-success/30'
              : 'bg-danger/20 text-danger border border-danger/30'
            }`}
          >
            {esNitida
              ? <><CheckCircle className="w-3.5 h-3.5" /> Nitidez OK ({varianza.toFixed(1)})</>
              : <><AlertTriangle className="w-3.5 h-3.5" /> Borrosidad ({varianza.toFixed(1)})</>
            }
          </div>
        )}
      </div>

      {/* Leyenda heatmap */}
      {vista !== 'original' && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-3 p-3 rounded-lg bg-surface/40 border border-white/10"
        >
          <div className="flex items-center justify-between mb-1.5">
            <span className="font-body text-white/60 text-xs">Baja activación</span>
            <span className="font-body text-white/60 text-xs">Alta activación</span>
          </div>
          <div className="h-3 rounded-full" style={{
            background: 'linear-gradient(to right, #000080, #0000ff, #00ffff, #00ff00, #ffff00, #ff8000, #ff0000)'
          }} />
          <p className="font-body text-white/40 text-[10px] mt-2 text-center">
            Las zonas cálidas (rojo/naranja) indican regiones donde la red neuronal detectó características patológicas
          </p>
        </motion.div>
      )}

      {/* Pills de patología para seleccionar Grad-CAM */}
      {patologiasSignificativas.length > 0 && (
        <div className="mt-3">
          <p className="font-body text-white/50 text-xs mb-2">Ver Grad-CAM por patología:</p>
          <div className="flex flex-wrap gap-1.5">
            {patologiasSignificativas.map(([nombre]) => {
              const englishKey = PATOLOGIAS_EN[nombre]
              const activa = patologiaSeleccionada === englishKey
              return (
                <button
                  key={nombre}
                  onClick={() => { onPatologiaChange(englishKey); setVista('overlay') }}
                  className={`px-2.5 py-1 rounded-full text-[11px] font-mono font-medium cursor-pointer transition-all
                    ${activa
                      ? 'bg-teal-med text-white'
                      : 'bg-white/10 text-white/60 hover:bg-white/20 hover:text-white/90'
                    }`}
                >
                  {nombre}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
