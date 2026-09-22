import { useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Check, Palette } from 'lucide-react'
import { useTheme } from '../../context/useTheme'

export default function ThemeSwitcher() {
  const { theme, setTheme, themes } = useTheme()
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)
  const reduceMotion = useReducedMotion()
  const activeTheme = themes.find(({ id }) => id === theme) || themes[0]

  const chooseTheme = (nextTheme, event) => {
    const rect = event.currentTarget.getBoundingClientRect()
    document.documentElement.style.setProperty('--theme-x', `${rect.left + rect.width / 2}px`)
    document.documentElement.style.setProperty('--theme-y', `${rect.top + rect.height / 2}px`)
    const update = () => flushSync(() => { setTheme(nextTheme); setOpen(false) })
    if (!reduceMotion && document.startViewTransition) document.startViewTransition(update)
    else update()
  }

  useEffect(() => {
    if (!open) return
    const closeOutside = (event) => {
      if (!containerRef.current?.contains(event.target)) setOpen(false)
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  return (
    <div className="theme-switcher" ref={containerRef}>
      <button
        type="button"
        className="theme-trigger"
        aria-label={`Tema actual: ${activeTheme.name}. Cambiar tema`}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Palette size={17} aria-hidden="true" />
        <span className="hidden md:inline">{activeTheme.name}</span>
        <span key={theme} className="theme-swatch" style={{ '--swatch': activeTheme.color }} aria-hidden="true" />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="theme-popover"
            role="listbox"
            aria-label="Tema de la interfaz"
            initial={reduceMotion ? false : { opacity: 0, transform: 'translateY(-8px) scale(.96)', filter: 'blur(3px)' }}
            animate={{ opacity: 1, transform: 'translateY(0) scale(1)', filter: 'blur(0)' }}
            exit={reduceMotion ? { opacity: 0 } : { opacity: 0, transform: 'translateY(-5px) scale(.98)', filter: 'blur(2px)' }}
            transition={{ duration: reduceMotion ? .08 : .22, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <p className="theme-popover__eyebrow">Apariencia</p>
            <p className="theme-popover__title">Elige un tema</p>
            <div className="theme-options">
              {themes.map((option) => (
                <button
                  type="button"
                  role="option"
                  aria-selected={option.id === theme}
                  className="theme-option"
                  key={option.id}
                  onClick={(event) => chooseTheme(option.id, event)}
                >
                  <span className={`theme-preview theme-preview--${option.id}`} aria-hidden="true">
                    <span /><span /><span />
                  </span>
                  <span>{option.name}</span>
                  {option.id === theme && <Check size={16} className="theme-option__check" aria-hidden="true" />}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}