import { Link, useLocation, useNavigate } from 'react-router-dom'
import { LogOut, Menu, ChevronRight } from 'lucide-react'
import { useAuth } from '../../context/useAuth'
const labels = {dashboard: 'Tablero', pacientes: 'Pacientes', estudios: 'Estudios', pendientes: 'Pendientes', actividad: 'Historial de movimientos', escaneo: 'Nuevo estudio', analisis: 'Análisis radiológico', informes: 'Informe', admin: 'Usuarios'}
export default function Navbar({open, onToggle, toggleRef}) {
  const {logout} = useAuth(), location = useLocation(), navigate = useNavigate()
  const label = labels[location.pathname.split('/')[1]] || 'Tablero'
  return <header className="app-navbar"><div className="flex items-center gap-3 min-w-0"><button ref={toggleRef} className="btn-secondary lg:hidden px-3" aria-expanded={open} aria-controls="app-navigation" aria-label="Abrir menú" onClick={onToggle}><Menu size={20}/></button><nav aria-label="Ubicación" className="flex items-center gap-2 text-sm text-slate-600"><Link to="/dashboard" className="hover:underline">NEO RX</Link><ChevronRight size={14}/><span className="font-semibold text-navy">{label}</span></nav></div><button className="btn-secondary shrink-0" onClick={() => {logout(); navigate('/login')}}><LogOut size={16}/><span className="hidden sm:inline">Cerrar sesión</span><span className="sr-only sm:hidden">Cerrar sesión</span></button></header>
}
