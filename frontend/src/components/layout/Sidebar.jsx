import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { LayoutDashboard, ScanLine, FolderOpen, Users, History, ListTodo, Settings, Wind, X } from 'lucide-react'
import { useAuth } from '../../context/useAuth'
const nav = [
  ['/dashboard', LayoutDashboard, 'Tablero'], ['/pacientes', Users, 'Pacientes'],
  ['/estudios', FolderOpen, 'Estudios'], ['/pendientes', ListTodo, 'Pendientes'],
  ['/escaneo', ScanLine, 'Nuevo estudio', ['recepcionista','medico']],
  ['/actividad', History, 'Historial de movimientos'],
  ['/admin/usuarios', Settings, 'Usuarios', ['administrador']],
]
const roles = {medico: 'Médico radiólogo', recepcionista: 'Recepcionista', administrador: 'Administrador'}
export default function Sidebar({open, onClose, sidebarRef}) {
  const {user, rol} = useAuth()
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 1023px)').matches)
  useEffect(() => {const media = window.matchMedia('(max-width: 1023px)'); const update = event => setMobile(event.matches); media.addEventListener('change', update); return () => media.removeEventListener('change', update)}, [])
  return <aside id="app-navigation" ref={sidebarRef} inert={mobile && !open} className={`app-sidebar ${open ? 'is-open' : ''}`} aria-label="Navegación principal">
    <div className="flex items-center gap-3 px-5 py-6 border-b border-white/15"><Wind size={28} className="text-sky-300"/><div><p className="font-heading font-bold text-xl">NEO RX</p><p className="text-xs text-slate-300">Gestión radiológica</p></div><button onClick={onClose} className="lg:hidden ml-auto p-2" aria-label="Cerrar menú"><X size={20}/></button></div>
    <nav className="flex-1 p-3 space-y-1">{nav.filter(item => !item[3] || item[3].includes(rol)).map(([to, Icon, label]) => <NavLink key={to} to={to} onClick={onClose} className={({isActive}) => `sidebar-link ${isActive ? 'active' : ''}`}><Icon size={19} aria-hidden="true"/><span>{label}</span></NavLink>)}</nav>
    <div className="border-t border-white/15 p-5"><p className="font-semibold text-sm truncate">{user}</p><p className="text-xs text-slate-300 mt-1">{roles[rol] || rol}</p></div>
  </aside>
}
