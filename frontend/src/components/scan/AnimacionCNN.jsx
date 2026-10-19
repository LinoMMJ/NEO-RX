/** Visualización neutral del flujo CNN; el modelo real se informa al terminar. */
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const CAPAS = [
  { id: 'input', name: 'ENTRADA', ch: '1 canal', desc: 'Radiografía normalizada', size: 'imagen', color: '#64748b' },
  { id: 'features1', name: 'RASGOS 1', ch: 'bordes', desc: 'Extracción de bordes y contraste', size: 'mapas', color: '#0EA5E9' },
  { id: 'features2', name: 'RASGOS 2', ch: 'texturas', desc: 'Detección de patrones pulmonares', size: 'mapas', color: '#38bdf8' },
  { id: 'features3', name: 'RASGOS 3', ch: 'formas', desc: 'Combinación de características', size: 'mapas', color: '#0EA5E9' },
  { id: 'final', name: 'MAPA FINAL', ch: 'activación', desc: 'Regiones relevantes para el modelo', size: 'mapas', color: '#f59e0b', gradcam: true },
  { id: 'output', name: 'SALIDA', ch: 'puntajes', desc: 'Puntuaciones por hallazgo', size: 'vector', color: '#10b981' },
]

// Textos de estado que cambian progresivamente durante el análisis
const ESTADOS = [
  { t: 400,  msg: 'Leyendo archivo DICOM…' },
  { t: 1400, msg: 'Validando nitidez técnica (varianza de Laplaciano)…' },
  { t: 2600, msg: 'Normalizando imagen al rango [-1024, 1024]…' },
  { t: 3800, msg: 'Extrayendo características con la red convolucional…' },
  { t: 5200, msg: 'Combinando patrones radiográficos…' },
  { t: 6800, msg: 'Calculando probabilidades para 12 patologías neumológicas…' },
]

export default function AnimacionCNN({ imagenPreview, progreso = 0, completado = false }) {
  const [capaActiva, setCapaActiva] = useState(0)
  const [mensaje, setMensaje] = useState(ESTADOS[0].msg)
  const [mensajeExtra, setMensajeExtra] = useState(null)

  // Ilumina capas secuencialmente — el tiempo total coincide con el análisis real
  useEffect(() => {
    const timers = []
    CAPAS.forEach((_, i) => {
      const delay = 600 + i * 800
      timers.push(setTimeout(() => setCapaActiva(i), delay))
    })
    return () => timers.forEach(clearTimeout)
  }, [])

  // Actualiza mensajes de estado en los tiempos indicados
  useEffect(() => {
    const timers = ESTADOS.map(({ t, msg }) =>
      setTimeout(() => setMensaje(msg), t)
    )
    return () => timers.forEach(clearTimeout)
  }, [])

  // Si tarda, conservar la solicitud en curso y explicar que no debe reenviarse.
  useEffect(() => {
    const timer = setTimeout(() => {
      setMensajeExtra('El análisis continúa en el servidor. No recargues ni envíes el estudio otra vez.')
    }, 30000)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="flex flex-col items-center justify-center min-h-[500px] p-6 bg-scan-bg rounded-2xl">
      {/* Título */}
      <div className="flex items-center gap-3 mb-8">
        <motion.div
          animate={{ scale: [1, 1.2, 1], opacity: [0.7, 1, 0.7] }}
          transition={{ repeat: Infinity, duration: 1.8 }}
          className="w-3 h-3 rounded-full bg-teal-med"
        />
        <h2 className="font-heading font-bold text-white text-xl tracking-wide">
          Analizando radiografía con CNN
        </h2>
      </div>

      <div className="flex gap-8 w-full max-w-4xl">
        {/* X-ray preview con efecto scan */}
        {imagenPreview && (
          <div className="relative w-28 h-28 rounded-lg overflow-hidden border border-white/20 flex-shrink-0">
            <img src={imagenPreview} alt="Radiografía" className="w-full h-full object-cover opacity-80" />
            {/* Línea de scan animada */}
            <motion.div
              className="absolute left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-teal-med to-transparent opacity-80"
              animate={{ top: ['0%', '100%', '0%'] }}
              transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}
            />
            <div className="absolute inset-0 bg-gradient-to-br from-teal-med/5 to-transparent" />
          </div>
        )}

        {/* Diagrama de capas CNN */}
        <div className="flex-1">
          <div className="flex items-center gap-1 flex-wrap">
            {CAPAS.map((capa, i) => {
              const activa = i === capaActiva
              const pasada = i < capaActiva
              return (
                <div key={capa.id} className="flex items-center">
                  <motion.div
                    animate={activa
                      ? { scale: 1.08, boxShadow: `0 0 18px ${capa.color}80` }
                      : { scale: 1, boxShadow: 'none' }
                    }
                    transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                    className={`
                      relative rounded-lg px-2.5 py-2 border text-center min-w-[64px]
                      transition-colors duration-300
                      ${activa
                        ? 'border-opacity-100 bg-opacity-20'
                        : pasada
                          ? 'border-white/20 bg-white/5'
                          : 'border-white/10 bg-transparent'
                      }
                    `}
                    style={activa ? {
                      borderColor: capa.color,
                      backgroundColor: `${capa.color}18`,
                    } : {}}
                  >
                    <p className="font-mono text-[10px] font-bold" style={{ color: activa ? capa.color : pasada ? '#94a3b8' : '#475569' }}>
                      {capa.name}
                    </p>
                    <p className="font-mono text-[9px] mt-0.5" style={{ color: activa ? capa.color : '#334155' }}>
                      {capa.ch}
                    </p>
                    {capa.gradcam && (
                      <div className="absolute -top-1.5 -right-1.5 bg-warning text-[8px] font-bold text-black px-1 rounded-sm leading-none py-0.5">
                        GRAD-CAM
                      </div>
                    )}
                  </motion.div>

                  {i < CAPAS.length - 1 && (
                    <motion.div
                      animate={{ opacity: pasada ? 1 : 0.3 }}
                      className="w-4 h-px mx-0.5"
                      style={{ backgroundColor: pasada ? '#0EA5E9' : '#334155' }}
                    />
                  )}
                </div>
              )
            })}
          </div>

          {/* Descripción de la capa activa */}
          <AnimatePresence mode="wait">
            <motion.div
              key={capaActiva}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-4 flex items-center gap-2"
            >
              <div className="w-1.5 h-1.5 rounded-full bg-teal-med" />
              <p className="font-body text-sm text-white/70">
                <span className="text-teal-med font-semibold">{CAPAS[capaActiva]?.name}</span>
                {' — '}{CAPAS[capaActiva]?.desc}
                <span className="text-white/30 ml-2 font-mono text-xs">{CAPAS[capaActiva]?.size}</span>
              </p>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* Mensaje de estado */}
      <div className="mt-8 w-full max-w-4xl">
        <AnimatePresence mode="wait">
          <motion.p
            key={mensaje}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="font-body text-sm text-white/60 h-5"
          >
            {mensaje}
          </motion.p>
        </AnimatePresence>

        {/* Barra de progreso */}
        <div className="mt-2 w-full h-2 bg-white/10 rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-teal-med to-sky-300"
            animate={{ width: completado ? '100%' : `${progreso}%` }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
          />
        </div>
        <p className="font-mono text-xs text-white/30 mt-1 text-right">
          {completado ? '100%' : `${Math.round(progreso)}%`}
        </p>
        {mensajeExtra && (
          <p className="font-mono text-xs text-warning/70 mt-2 text-center animate-pulse">
            {mensajeExtra}
          </p>
        )}
      </div>

      {/* Nota técnica para la tesis */}
      <p className="mt-6 font-mono text-[10px] text-white/25 text-center">
        Modelo torácico preentrenado · El detalle técnico real se mostrará con el resultado
      </p>
    </div>
  )
}
