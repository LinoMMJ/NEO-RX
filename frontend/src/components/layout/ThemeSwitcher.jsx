import { useEffect, useRef, useState } from 'react'
import { Check, Palette } from 'lucide-react'
import { useTheme } from '../../context/useTheme'

export default function ThemeSwitcher() {
  const { theme, setTheme, themes } = useTheme()
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)
  const activeTheme = themes.find(({ id }) => id === theme) || themes[0]

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
        <span className="theme-swatch" style={{ '--swatch': activeTheme.color }} aria-hidden="true" />
      </button>

      {open && (
        <div className="theme-popover" role="listbox" aria-label="Tema de la interfaz">
          <p className="theme-popover__eyebrow">Apariencia</p>
          <p className="theme-popover__title">Elige un ambiente</p>
          <div className="theme-options">
            {themes.map((option) => (
              <button
                type="button"
                role="option"
                aria-selected={option.id === theme}
                className="theme-option"
                key={option.id}
                onClick={() => { setTheme(option.id); setOpen(false) }}
              >
                <span className={`theme-preview theme-preview--${option.id}`} aria-hidden="true">
                  <span /><span /><span />
                </span>
                <span>{option.name}</span>
                {option.id === theme && <Check size={16} className="theme-option__check" aria-hidden="true" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
