import { useState, useCallback, useRef, useMemo, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, CheckCircle, Info, X } from 'lucide-react'

import { ToastContext } from './useToast'

const ESTILOS = {
  error:   { icon: AlertTriangle, cls: 'bg-danger text-white',  ring: 'ring-danger/30' },
  success: { icon: CheckCircle,   cls: 'bg-success text-white', ring: 'ring-success/30' },
  info:    { icon: Info,          cls: 'bg-navy text-white',    ring: 'ring-navy/30' },
}

const MENSAJE_RED =
  'Error de conexión con el servidor. Verifica que el backend esté activo.'

let _id = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef({})

  const dismiss = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id))
    clearTimeout(timers.current[id])
    delete timers.current[id]
  }, [])

  const push = useCallback((tipo, mensaje, ttl = 4500) => {
    const id = ++_id
    setToasts((t) => [...t, { id, tipo, mensaje }])
    timers.current[id] = setTimeout(() => dismiss(id), ttl)
    return id
  }, [dismiss])

  // API pública: nunca expone stack traces al usuario
  const toast = useMemo(() => ({
    error:   (m) => push('error', m || MENSAJE_RED),
    success: (m) => push('success', m),
    info:    (m) => push('info', m),
    red:     () => push('error', MENSAJE_RED),
  }), [push])
  useEffect(() => { const pending = timers.current; return () => Object.values(pending).forEach(clearTimeout) }, [])

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div
        className="fixed top-4 left-1/2 -translate-x-1/2 z-[1000] flex flex-col items-center gap-2 w-full max-w-md px-4 pointer-events-none"
        aria-live="polite"
        aria-atomic="true"
      >
        <AnimatePresence>
          {toasts.map(({ id, tipo, mensaje }) => {
            const { icon: Icon, cls, ring } = ESTILOS[tipo] || ESTILOS.info
            return (
              <motion.div
                key={id}
                role="alert"
                layout
                initial={{ opacity: 0, y: -16, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -12, scale: 0.96 }}
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                className={`pointer-events-auto w-full flex items-start gap-3 px-4 py-3 rounded-xl shadow-lg ring-1 ${ring} ${cls}`}
              >
                <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <p className="font-body text-sm leading-snug flex-1">{mensaje}</p>
                <button
                  onClick={() => dismiss(id)}
                  className="flex-shrink-0 opacity-70 hover:opacity-100 transition-opacity cursor-pointer"
                  aria-label="Cerrar notificación"
                >
                  <X className="w-4 h-4" />
                </button>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
