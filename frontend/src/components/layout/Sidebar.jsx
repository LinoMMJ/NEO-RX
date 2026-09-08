import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, ScanLine, FolderOpen, Users, FileText,
  ChevronRight, Wind,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

const NAV = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/escaneo',    icon: ScanLine,        label: 'Nuevo Escaneo' },
  { to: '/estudios',   icon: FolderOpen,      label: 'Estudios' },
  { to: '/pacientes',  icon: Users,           label: 'Pacientes' },
  { to: '/informes',   icon: FileText,        label: 'Informes',  roles: ['medico'] },
]

const ROL_LABEL = { medico: 'Médico Radiólogo', tecnico: 'Técnico Radiólogo', administrador: 'Administrador' }
const ROL_COLOR = { medico: 'bg-teal-med', tecnico: 'bg-warning', administrador: 'bg-success' }

export default function Sidebar() {
  const [expanded, setExpanded] = useState(false)
  const { user, rol } = useAuth()

  const items = NAV.filter(n => !n.roles || n.roles.includes(rol))

  return (
    <motion.aside
      animate={{ width: expanded ? 240 : 72 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="fixed left-0 top-0 h-full z-40 flex flex-col bg-sidebar overflow-hidden select-none"
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-white/10">
        <div className="w-9 h-9 rounded-lg bg-teal-med/20 border border-teal-med/40 flex items-center justify-center flex-shrink-0">
          <Wind className="w-5 h-5 text-teal-med" />
        </div>
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <p className="font-heading font-bold text-white text-base leading-none">NEO RX</p>
              <p className="font-body text-white/40 text-[10px] mt-0.5">Diagnóstico Radiológico</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 flex flex-col gap-1 px-2">
        {items.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 group
             ${isActive
               ? 'bg-teal-med/20 text-teal-med'
               : 'text-white/50 hover:bg-white/8 hover:text-white/90'}`
          }>
            {({ isActive }) => (
              <>
                <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-teal-med' : ''}`} />
                <AnimatePresence>
                  {expanded && (
                    <motion.span
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.12 }}
                      className="font-body font-medium text-sm whitespace-nowrap"
                    >
                      {label}
                    </motion.span>
                  )}
                </AnimatePresence>
                {isActive && (
                  <motion.div layoutId="activeIndicator" className="ml-auto w-1.5 h-1.5 rounded-full bg-teal-med flex-shrink-0" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Usuario */}
      <div className="border-t border-white/10 px-3 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-navy flex items-center justify-center flex-shrink-0">
            <span className="font-heading font-bold text-teal-med text-xs">
              {user?.[0]?.toUpperCase() || 'U'}
            </span>
          </div>
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="min-w-0"
              >
                <p className="font-body text-white/90 text-xs font-semibold truncate">{user}</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${ROL_COLOR[rol] || 'bg-slate-500'}`} />
                  <p className="font-body text-white/40 text-[10px] truncate">{ROL_LABEL[rol] || rol}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.aside>
  )
}
