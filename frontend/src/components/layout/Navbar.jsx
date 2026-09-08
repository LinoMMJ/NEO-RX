import { useLocation } from 'react-router-dom'
import { LogOut, ChevronRight } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useNavigate } from 'react-router-dom'

const BREADCRUMBS = {
  '/dashboard':  ['Dashboard'],
  '/escaneo':    ['Dashboard', 'Nuevo Escaneo'],
  '/pacientes':  ['Dashboard', 'Pacientes'],
  '/informes':   ['Dashboard', 'Informes'],
  '/estudios':   ['Dashboard', 'Estudios'],
}

export default function Navbar() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const crumbs = BREADCRUMBS[location.pathname] || ['Dashboard']

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 sticky top-0 z-30">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1" aria-label="breadcrumb">
        <span className="font-heading font-semibold text-navy text-sm">Neo Rayos X Digital</span>
        {crumbs.map((c, i) => (
          <span key={i} className="flex items-center gap-1">
            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
            <span className={`font-body text-sm ${i === crumbs.length - 1 ? 'text-teal-med font-semibold' : 'text-slate-500'}`}>{c}</span>
          </span>
        ))}
      </nav>

      {/* Usuario + logout */}
      <div className="flex items-center gap-3">
        <div className="text-right">
          <p className="font-body text-sm font-semibold text-navy leading-none">{user}</p>
          <p className="font-body text-xs text-slate-400 mt-0.5">Centro Neo Rayos X Digital</p>
        </div>
        <button
          onClick={handleLogout}
          className="p-2 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
          aria-label="Cerrar sesión"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
