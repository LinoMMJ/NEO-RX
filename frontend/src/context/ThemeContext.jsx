import { useCallback, useEffect, useMemo, useState } from 'react'
import { ThemeContext } from './useTheme'

const THEMES = [
  { id: 'clinical', name: 'Claro clínico', color: '#0f78b8' },
  { id: 'dark', name: 'Oscuro', color: '#111b2c' },
  { id: 'electric', name: 'Azul eléctrico', color: '#006cff' },
  { id: 'graphite', name: 'Grafito', color: '#3f4857' },
]

const validThemes = new Set(THEMES.map(({ id }) => id))

function initialTheme() {
  try {
    const stored = localStorage.getItem('neorx-theme')
    return validThemes.has(stored) ? stored : 'clinical'
  } catch {
    return 'clinical'
  }
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(initialTheme)

  const setTheme = useCallback((nextTheme) => {
    if (validThemes.has(nextTheme)) setThemeState(nextTheme)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme === 'clinical' ? 'light' : 'dark'
    try { localStorage.setItem('neorx-theme', theme) } catch { /* La preferencia sigue activa durante la sesión. */ }
  }, [theme])

  const value = useMemo(() => ({ theme, setTheme, themes: THEMES }), [theme, setTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
