import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import ThemeSwitcher from '../components/layout/ThemeSwitcher'
import { ThemeProvider } from '../context/ThemeContext'

describe('selector de temas', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  it('muestra las siete paletas y guarda la selección hospitalaria', async () => {
    render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>)
    fireEvent.click(screen.getByRole('button', { name: /Tema actual:/ }))
    expect(screen.getAllByRole('option')).toHaveLength(7)
    fireEvent.click(screen.getByRole('option', { name: 'Hospital' }))

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('hospital'))
    expect(document.documentElement.style.colorScheme).toBe('light')
    expect(localStorage.getItem('neorx-theme')).toBe('hospital')
  })

  it('restaura un tema oscuro guardado', async () => {
    localStorage.setItem('neorx-theme', 'electric')
    render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>)

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('electric'))
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(screen.getByRole('button', { name: /Eléctrico/ })).toBeInTheDocument()
  })
})