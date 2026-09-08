import { motion } from 'framer-motion'

/**
 * IndicadorHallazgo — Círculo animado que marca el hallazgo principal
 * en las coordenadas que retorna el endpoint Grad-CAM (centroide).
 */
export default function IndicadorHallazgo({ centroide, imagen512Size = 400 }) {
  if (!centroide) return null
  // Escalar de 512px (tamaño del mapa) al tamaño real del contenedor
  const scale = imagen512Size / 512
  const x = centroide.x * scale
  const y = centroide.y * scale

  return (
    <motion.div
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.5 }}
      className="absolute pointer-events-none"
      style={{ left: x - 18, top: y - 18 }}
    >
      {/* Círculo exterior pulsante */}
      <motion.div
        animate={{ scale: [1, 1.3, 1], opacity: [0.6, 0.3, 0.6] }}
        transition={{ repeat: Infinity, duration: 2 }}
        className="absolute inset-0 w-9 h-9 rounded-full border-2 border-yellow-400"
      />
      {/* Punto central */}
      <div className="w-2 h-2 rounded-full bg-yellow-400 absolute"
           style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }} />
    </motion.div>
  )
}
