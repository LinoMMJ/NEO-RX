import { motion } from 'framer-motion'

/**
 * ChestXray — Ilustración anatómica de radiografía de tórax en SVG puro.
 * Líneas de costillas, campos pulmonares, columna y silueta cardíaca que se
 * dibujan progresivamente, con una línea de barrido (scan) en bucle.
 * Sin imágenes externas: 100% vectorial, nítida en cualquier resolución.
 */
export default function ChestXray({ className = '' }) {
  const reduce =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  const draw = (delay) => ({
    hidden: { pathLength: 0, opacity: 0 },
    show: {
      pathLength: 1,
      opacity: 1,
      transition: { pathLength: { duration: 2, delay, ease: 'easeInOut' }, opacity: { duration: 0.4, delay } },
    },
  })

  // Pares de costillas (curvas Bézier espejadas)
  const costillas = [0, 1, 2, 3, 4, 5]

  return (
    <svg viewBox="0 0 400 460" className={className} aria-hidden="true" fill="none">
      <defs>
        <linearGradient id="xrayGlow" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#0EA5E9" stopOpacity="0.4" />
        </linearGradient>
        <radialGradient id="xrayBg" cx="50%" cy="42%" r="60%">
          <stop offset="0%" stopColor="#102a43" />
          <stop offset="100%" stopColor="#0A1628" stopOpacity="0" />
        </radialGradient>
      </defs>

      <rect x="0" y="0" width="400" height="460" fill="url(#xrayBg)" />

      <motion.g
        initial="hidden"
        animate="show"
        stroke="url(#xrayGlow)"
        strokeWidth="1.6"
        strokeLinecap="round"
      >
        {/* Columna vertebral */}
        <motion.line x1="200" y1="40" x2="200" y2="400" variants={draw(0.1)} strokeWidth="2" />
        {[...Array(11)].map((_, i) => (
          <motion.line
            key={`vert-${i}`}
            x1="190" y1={62 + i * 30} x2="210" y2={62 + i * 30}
            variants={draw(0.2 + i * 0.03)}
            strokeWidth="1.2"
          />
        ))}

        {/* Campos pulmonares */}
        <motion.path
          d="M188 90 C120 95, 95 170, 100 250 C103 305, 130 350, 175 355 C186 356, 188 330, 188 300 Z"
          variants={draw(0.3)} strokeWidth="2"
        />
        <motion.path
          d="M212 90 C280 95, 305 170, 300 250 C297 305, 270 350, 225 355 C214 356, 212 330, 212 300 Z"
          variants={draw(0.3)} strokeWidth="2"
        />

        {/* Costillas izquierdas y derechas */}
        {costillas.map((i) => {
          const y = 110 + i * 35
          return (
            <g key={`rib-${i}`}>
              <motion.path
                d={`M196 ${y} C150 ${y - 4}, 110 ${y + 18}, 96 ${y + 48}`}
                variants={draw(0.5 + i * 0.08)} strokeWidth="1.4"
              />
              <motion.path
                d={`M204 ${y} C250 ${y - 4}, 290 ${y + 18}, 304 ${y + 48}`}
                variants={draw(0.5 + i * 0.08)} strokeWidth="1.4"
              />
            </g>
          )
        })}

        {/* Clavículas */}
        <motion.path d="M120 92 C155 78, 185 80, 198 86" variants={draw(0.4)} strokeWidth="1.6" />
        <motion.path d="M280 92 C245 78, 215 80, 202 86" variants={draw(0.4)} strokeWidth="1.6" />

        {/* Silueta cardíaca */}
        <motion.path
          d="M200 250 C175 250, 158 275, 165 305 C172 332, 200 345, 200 345 C200 345, 222 330, 226 302 C230 278, 220 250, 200 250 Z"
          variants={draw(1.2)} strokeWidth="1.5" stroke="#5eead4"
        />

        {/* Diafragma */}
        <motion.path d="M100 350 C140 372, 175 372, 195 358" variants={draw(1)} strokeWidth="1.4" />
        <motion.path d="M300 350 C260 372, 225 372, 205 358" variants={draw(1)} strokeWidth="1.4" />
      </motion.g>

      {/* Línea de barrido en bucle */}
      {!reduce && (
        <motion.g
          initial={{ y: 0 }}
          animate={{ y: [0, 380, 0] }}
          transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut', delay: 2.4 }}
        >
          <rect x="60" y="40" width="280" height="2" fill="#38bdf8" opacity="0.9" />
          <rect x="60" y="42" width="280" height="22" fill="url(#xrayGlow)" opacity="0.12" />
        </motion.g>
      )}
    </svg>
  )
}
