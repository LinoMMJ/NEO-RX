import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  BrainCircuit,
  FileText,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Plus,
  ScanLine,
  ShieldCheck,
  Users,
  X,
} from 'lucide-react'
import { useAuth } from '../../context/useAuth'

const navigation = [
  {
    label: 'Inicio',
    icon: LayoutDashboard,
    items: [
      { to: '/dashboard', label: 'Tablero' },
      { to: '/actividad', label: 'Actividad reciente' },
    ],
  },
  {
    label: 'Pacientes',
    icon: Users,
    items: [
      { to: '/pacientes', label: 'Todos los pacientes' },
      { to: '/pacientes?accion=nuevo', label: 'Registrar paciente' },
    ],
  },
  {
    label: 'Estudios',
    icon: FolderOpen,
    items: [
      { to: '/estudios', label: 'Todos los estudios' },
      { to: '/estudios?estado=pendiente', label: 'Pendientes' },
      { to: '/estudios?estado=en_proceso', label: 'En análisis' },
      { to: '/estudios?estado=completado&vista=validados', label: 'Validados' },
      { to: '/estudios?estado=requiere_repeticion', label: 'Repetición técnica' },
      { to: '/escaneo', label: 'Analizar tórax (DICOM / PNG)', roles: ['medico', 'recepcionista'] },
      { to: '/estudios/registrar', label: 'Registrar estudio sin IA', roles: ['medico', 'recepcionista'] },
    ],
  },
  {
    label: 'Análisis',
    icon: BrainCircuit,
    items: [
      { to: '/pendientes?cola=procesamiento', label: 'Por procesar' },
      { to: '/pendientes?cola=errores', label: 'Errores de procesamiento' },
      { to: '/estudios?estado=completado&vista=ia', label: 'Resultados de IA' },
    ],
  },
  {
    label: 'Informes',
    icon: FileText,
    roles: ['medico'],
    items: [
      { to: '/informes', label: 'Todos los informes' },
      { to: '/informes?estado=borrador', label: 'Borradores' },
      { to: '/informes?estado=revisado', label: 'Pendientes de firma' },
      { to: '/informes?estado=firmado', label: 'Validados y firmados' },
    ],
  },
  {
    label: 'Administración',
    icon: ShieldCheck,
    roles: ['administrador'],
    items: [
      { to: '/dashboard?vista=administracion', label: 'Resumen administrativo' },
      { to: '/admin/usuarios', label: 'Usuarios' },
      { to: '/actividad', label: 'Auditoría' },
    ],
  },
]

const roleLabels = {
  medico: 'Médico radiólogo',
  recepcionista: 'Recepcionista',
  administrador: 'Administrador',
}

function initials(value) {
  return String(value || 'Usuario').trim().split(/\s+/).slice(0, 2)
    .map(part => part[0]?.toUpperCase()).join('') || 'U'
}

function isActive(item, location) {
  const [path, query = ''] = item.to.split('?')
  if (location.pathname !== path) return false
  const expected = new URLSearchParams(query)
  const current = new URLSearchParams(location.search)
  if (![...expected.keys()].length) return !location.search
  return [...expected.entries()].every(([key, value]) => current.get(key) === value)
}

export default function Sidebar({ open, onClose, sidebarRef }) {
  const { user, rol, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 1023px)').matches)

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1023px)')
    const update = event => setMobile(event.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  const groups = navigation
    .filter(group => !group.roles || group.roles.includes(rol))
    .map(group => ({
      ...group,
      items: group.items.filter(item => !item.roles || item.roles.includes(rol)),
    }))
    .filter(group => group.items.length)

  function signOut() {
    logout()
    navigate('/login')
  }

  return (
    <aside id="app-navigation" ref={sidebarRef} inert={mobile && !open} className={`app-sidebar sidebar-shell ${open ? 'is-open' : ''}`} aria-label="Navegación principal">
      <header className="sidebar-brand">
        <span className="sidebar-brand-mark" aria-hidden="true"><ScanLine size={23} /></span>
        <span className="sidebar-brand-copy"><strong>NEO RX</strong><small>Sistema radiológico</small></span>
        <button onClick={onClose} className="sidebar-close lg:hidden" aria-label="Cerrar menú"><X size={19} /></button>
      </header>

      {(rol === 'recepcionista' || rol === 'medico') && (
        <div className="sidebar-primary-action">
          <Link to="/escaneo" onClick={onClose} className="sidebar-new-study"><Plus size={18} aria-hidden="true" /><span>Nuevo estudio</span></Link>
        </div>
      )}

      <nav className="sidebar-navigation">
        {groups.map(group => {
          const groupActive = group.items.some(item => isActive(item, location))
          const Icon = group.icon
          return (
            <section className={`sidebar-module ${groupActive ? 'is-active' : ''}`} key={group.label} aria-labelledby={`sidebar-${group.label.toLowerCase().replace('ó', 'o')}`}>
              <h2 id={`sidebar-${group.label.toLowerCase().replace('ó', 'o')}`} className="sidebar-module-title">
                <span className="sidebar-module-icon" aria-hidden="true"><Icon size={17} strokeWidth={1.9} /></span>
                <span>{group.label}</span>
              </h2>
              <div className="sidebar-subnav">
                {group.items.map(item => {
                  const active = isActive(item, location)
                  return (
                    <Link key={`${group.label}-${item.to}`} to={item.to} onClick={onClose} aria-current={active ? 'page' : undefined} className={`sidebar-sublink ${active ? 'active' : ''}`}>
                      <span>{item.label}</span>
                    </Link>
                  )
                })}
              </div>
            </section>
          )
        })}
      </nav>

      <footer className="sidebar-account">
        <div className="sidebar-avatar" aria-hidden="true">{initials(user)}</div>
        <div className="sidebar-account-copy"><strong title={user || 'Usuario'}>{user || 'Usuario'}</strong><span>{roleLabels[rol] || rol}</span></div>
        <button className="sidebar-logout" onClick={signOut} aria-label="Cerrar sesión" title="Cerrar sesión"><LogOut size={18} /></button>
      </footer>
    </aside>
  )
}
