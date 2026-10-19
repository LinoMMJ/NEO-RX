import { Link, useLocation } from 'react-router-dom'
import { Menu, ChevronRight } from 'lucide-react'
import ThemeSwitcher from './ThemeSwitcher'

const labels = {dashboard: 'Inicio', pacientes: 'Pacientes', estudios: 'Estudios', pendientes: 'Pendientes', actividad: 'Actividad', escaneo: 'Nuevo estudio', analisis: 'Análisis radiológico', informes: 'Informes', admin: 'Usuarios'}

export default function Navbar({open, onToggle, toggleRef}) {
  const location = useLocation()
  const label = labels[location.pathname.split('/')[1]] || 'Inicio'
  return <header className="app-navbar"><div className="flex items-center gap-3 min-w-0"><button ref={toggleRef} className="btn-secondary lg:hidden px-3" aria-expanded={open} aria-controls="app-navigation" aria-label="Abrir menú" onClick={onToggle}><Menu size={20}/></button><nav aria-label="Ubicación" className="flex items-center gap-2 text-sm text-slate-600"><Link to="/dashboard" className="hover:underline">NEO RX</Link><ChevronRight size={14}/><span className="font-semibold text-navy">{label}</span></nav></div><div className="navbar-actions"><ThemeSwitcher/></div></header>
}
