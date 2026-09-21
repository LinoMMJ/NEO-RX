import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import {
  Plus, Search, Edit, Lock, AlertCircle,
  ChevronDown, ChevronUp, Mail, Shield, UserCheck, UserX
} from 'lucide-react'
import { api } from '../api'
import { useResource } from '../hooks/useWorkspace'
import { errorMessage, fieldErrors } from '../api/errors'
import { useToast } from '../context/useToast'

const ROL_LABELS = {
  medico: 'Médico Radiólogo',
  recepcionista: 'Recepcionista',
  administrador: 'Administrador',
}

const ROL_COLORS = {
  medico: 'bg-emerald-100 text-emerald-700',
  recepcionista: 'bg-blue-100 text-blue-700',
  administrador: 'bg-violet-100 text-violet-700',
}

const ROL_ICONS = {
  medico: Shield,
  recepcionista: Mail,
  administrador: UserCheck,
}

export default function AdminUsuariosPage() {
  const toast = useToast()
  const dialogRef = useRef(null)
  const [formError, setFormError] = useState('')
  const [formErrors, setFormErrors] = useState({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [search, setSearch] = useState('')
  const [rolFilter, setRolFilter] = useState('')
  const [activoFilter, setActivoFilter] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [formData, setFormData] = useState({ username: '', email: '', first_name: '', last_name: '', rol: 'recepcionista', is_active: true, password: '' })
  const [submitting, setSubmitting] = useState(false)
  const [sortField, setSortField] = useState('date_joined')
  const [sortDir, setSortDir] = useState('desc')
  const [showPassword, setShowPassword] = useState(false)
  const [resetPasswordUser, setResetPasswordUser] = useState(null)

  const [revision, setRevision] = useState(0)
  const {data, loading, error} = useResource('/admin/users/', {page, page_size: pageSize, search, rol: rolFilter, is_active: activoFilter, ordering: `${sortDir === 'desc' ? '-' : ''}${sortField}`}, revision)
  const usuarios = data?.results || [], total = data?.count ?? 0
  const fetchUsuarios = async () => setRevision(v => v + 1)

  useEffect(() => {
    if (!showModal) return
    const previous = document.activeElement
    const dialog = dialogRef.current
    dialog?.querySelector('input')?.focus()
    const keyboard = event => {
      if (event.key === 'Escape') { setShowModal(false); return }
      if (event.key !== 'Tab') return
      const elements = [...dialog.querySelectorAll('input:not([disabled]), select:not([disabled]), button:not([disabled]), a[href]')]
      const first = elements[0], last = elements.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    dialog?.addEventListener('keydown', keyboard)
    return () => { dialog?.removeEventListener('keydown', keyboard); previous?.focus() }
  }, [showModal])

  const handleSort = (field) => {
    if (!field) return
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortField(field); setSortDir('asc') }
  }

  const openCreateModal = () => {
    setFormError(''); setFormErrors({})
    setEditingUser(null)
    setFormData({ username: '', email: '', first_name: '', last_name: '', rol: 'recepcionista', is_active: true, password: '' })
    setShowModal(true)
  }

  const openEditModal = (user) => {
    setFormError(''); setFormErrors({})
    setEditingUser(user)
    setFormData({ username: user.username, email: user.email || '', first_name: user.first_name || '', last_name: user.last_name || '', rol: user.rol, is_active: user.is_active, password: '' })
    setShowModal(true)
  }

  const closeModal = () => { setShowModal(false); setEditingUser(null) }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setFormError(''); setFormErrors({})
    try {
      const payload = { ...formData }
      if (!payload.password) delete payload.password
      if (editingUser) {
        await api.patch(`/admin/users/${editingUser.id}/`, payload)
      } else {
        await api.post('/admin/users/', payload)
      }
      toast.success(editingUser ? 'Usuario actualizado.' : 'Usuario creado.')
      closeModal()
      await fetchUsuarios()
    } catch (err) {
      setFormError(errorMessage(err)); setFormErrors(fieldErrors(err)); document.getElementById(`user-${Object.keys(fieldErrors(err))[0]}`)?.focus()
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleActive = async (user) => {
    try {
      await api.post(`/admin/users/${user.id}/toggle_active/`)
      fetchUsuarios()
    } catch (err) { toast.error(errorMessage(err)) }
  }

  const handleResetPassword = async (user) => {
    setResetPasswordUser(user.id)
    try {
      const res = await api.post(`/admin/users/${user.id}/reset_password/`)
      alert(`Password temporal para ${user.username}:\n\n${res.data.temporary_password}\n\nCópiala ahora, no se mostrará de nuevo.`)
    } catch (err) { toast.error(errorMessage(err)) }
    setResetPasswordUser(null)
  }

  return (
    <div className="workspace">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-navy">Administración de Usuarios</h1>
          <p className="font-body text-sm text-slate-500 mt-1">Gestión de cuentas del sistema (solo administradores)</p>
        </div>
        <button onClick={openCreateModal} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Nuevo usuario
        </button>
      </div>

      {/* Alerts */}
      {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2"><AlertCircle className="w-5 h-5" />{error}</div>}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              aria-label="Buscar usuarios"
              placeholder="Buscar por nombre, correo o usuario…"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
              className="input w-full pl-10 pr-4 py-2"
            />
          </div>
          <select
            aria-label="Filtrar por rol"
            value={rolFilter}
            onChange={e => { setRolFilter(e.target.value); setPage(1) }}
            className="input py-2"
          >
            <option value="">Todos los roles</option>
            <option value="medico">Médico Radiólogo</option>
            <option value="recepcionista">Recepcionista</option>
            <option value="administrador">Administrador</option>
          </select>
          <select
            aria-label="Filtrar por estado"
            value={activoFilter}
            onChange={e => { setActivoFilter(e.target.value); setPage(1) }}
            className="input py-2"
          >
            <option value="">Todos los estados</option>
            <option value="true">Activos</option>
            <option value="false">Inactivos</option>
          </select>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span>{total} usuarios</span>
            <select aria-label="Usuarios por página" value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1) }} className="input py-1 w-20">
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={25}>25</option>
            </select>
            por página
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center"><div className="animate-spin w-8 h-8 border-2 border-navy border-t-transparent rounded-full mx-auto" /></div>
        ) : usuarios.length === 0 ? (
          <div className="p-8 text-center text-slate-400">No se encontraron usuarios</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  {[
                    { key: 'username', label: 'Usuario' },
                    { key: 'email', label: 'Email' },
                    { key: 'first_name', label: 'Nombre' },
                    { key: 'rol', label: 'Rol' },
                    { key: 'is_active', label: 'Estado' },
                    { key: 'date_joined', label: 'Creado' },
                    { key: 'actions', label: '' },
                  ].map(col => (
                    <th key={col.key} scope="col" aria-sort={sortField === col.key ? (sortDir === "asc" ? "ascending" : "descending") : undefined} className="px-4 py-3 text-left text-sm font-semibold text-slate-600">
                      {["username","email","first_name","date_joined"].includes(col.key) ? <button type="button" className="flex items-center gap-1" onClick={() => handleSort(col.key)}>
                        {col.label || "Acciones"}
                        {sortField === (col.key === 'username' ? 'username' : col.key === 'email' ? 'email' : col.key === 'first_name' ? 'first_name' : col.key === 'date_joined' ? 'date_joined' : null) && (
                          sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
                        )}
                      </button> : <span>{col.label || "Acciones"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {usuarios.map((user, i) => (
                  <motion.tr key={user.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                    <td className="px-4 py-3">
                      <div className="font-mono font-medium text-navy">{user.username}</div></td>
                    <td className="px-4 py-3 font-body text-sm text-slate-600">{user.email || '—'}</td>
                    <td className="px-4 py-3 font-body text-sm text-slate-700">{[user.first_name, user.last_name].filter(Boolean).join(' ') || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${ROL_COLORS[user.rol]}`}>
                        {(() => { const RolIcon = ROL_ICONS[user.rol]; return <RolIcon className="w-3 h-3" /> })()}
                        {ROL_LABELS[user.rol]}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${user.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                        {user.is_active ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                        {user.is_active ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-body text-sm text-slate-500">{new Date(user.date_joined).toLocaleDateString('es-BO')}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button onClick={() => openEditModal(user)} className="min-h-11 min-w-11 p-2 text-slate-600 hover:text-navy hover:bg-slate-100 rounded-lg transition" aria-label={`Editar a ${user.username}`} title="Editar"><Edit className="w-4 h-4" /></button>
                        <button onClick={() => handleToggleActive(user)} className={`min-h-11 min-w-11 p-2 ${user.is_active ? 'text-orange-800 hover:text-orange-900' : 'text-emerald-800 hover:text-emerald-900'} hover:bg-slate-100 rounded-lg transition`} aria-label={`${user.is_active ? 'Desactivar' : 'Activar'} a ${user.username}`} title={user.is_active ? 'Desactivar' : 'Activar'}>{user.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}</button>
                        <button onClick={() => handleResetPassword(user)} disabled={resetPasswordUser === user.id} className={`min-h-11 min-w-11 p-2 ${resetPasswordUser === user.id ? 'text-slate-300 cursor-not-allowed' : 'text-blue-800 hover:text-blue-900'} hover:bg-slate-100 rounded-lg transition`} aria-label={`Restablecer contraseña de ${user.username}`} title="Restablecer contraseña"><Lock className="w-4 h-4" /></button>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {total > pageSize && (
          <div className="px-4 py-3 border-t border-slate-200 flex items-center justify-between">
            <span className="font-body text-sm text-slate-500">Mostrando {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, total)} de {total}</span>
            <div className="flex gap-1">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary px-3 py-1 text-sm">Anterior</button>
              <button onClick={() => setPage(p => p + 1)} disabled={page * pageSize >= total} className="btn-secondary px-3 py-1 text-sm">Siguiente</button>
            </div>
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={closeModal}>
          <motion.div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="user-modal-title" tabIndex={-1} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="bg-white rounded-2xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-slate-200 flex items-center justify-between">
              <h2 id="user-modal-title" className="font-heading text-xl font-bold text-navy">{editingUser ? 'Editar usuario' : 'Nuevo usuario'}</h2>
              <button aria-label="Cerrar formulario" onClick={closeModal} className="p-2 text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {formError && <p role="alert" className="bg-red-50 text-red-700 p-3 rounded-lg">{formError}</p>}
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="user-username" className="label">Usuario *</label>
                  <input id="user-username" aria-invalid={!!formErrors.username} aria-describedby={formErrors.username ? "user-error-username" : undefined} type="text" value={formData.username} onChange={e => setFormData({...formData, username: e.target.value})} className="input mt-1" required />
                  {formErrors.username && <p id="user-error-username" className="text-red-700 text-sm">{String(formErrors.username)}</p>}
                </div>
                <div>
                  <label htmlFor="user-email" className="label">Email (para recuperación)</label>
                  <input id="user-email" aria-invalid={!!formErrors.email} aria-describedby={formErrors.email ? "user-error-email" : undefined} type="email" value={formData.email} onChange={e => setFormData({...formData, email: e.target.value})} className="input mt-1" />
                  {formErrors.email && <p id="user-error-email" className="text-red-700 text-sm">{String(formErrors.email)}</p>}
                </div>
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="user-first_name" className="label">Nombres</label>
                  <input id="user-first_name" aria-invalid={!!formErrors.first_name} aria-describedby={formErrors.first_name ? "user-error-first_name" : undefined} type="text" value={formData.first_name} onChange={e => setFormData({...formData, first_name: e.target.value})} className="input mt-1" />
                  {formErrors.first_name && <p id="user-error-first_name" className="text-red-700 text-sm">{String(formErrors.first_name)}</p>}
                </div>
                <div>
                  <label htmlFor="user-last_name" className="label">Apellidos</label>
                  <input id="user-last_name" aria-invalid={!!formErrors.last_name} aria-describedby={formErrors.last_name ? "user-error-last_name" : undefined} type="text" value={formData.last_name} onChange={e => setFormData({...formData, last_name: e.target.value})} className="input mt-1" />
                  {formErrors.last_name && <p id="user-error-last_name" className="text-red-700 text-sm">{String(formErrors.last_name)}</p>}
                </div>
              </div>
              <div>
                <label htmlFor="user-rol" className="label">Rol *</label>
                <select id="user-rol" value={formData.rol} onChange={e => setFormData({...formData, rol: e.target.value})} className="input mt-1">
                  <option value="recepcionista">Recepcionista</option>
                  <option value="medico">Médico Radiólogo</option>
                  <option value="administrador">Administrador</option>
                </select>
              </div>
              <label className="flex gap-2 items-center min-h-11"><input type="checkbox" checked={formData.is_active} onChange={e => setFormData({ ...formData, is_active: e.target.checked })} />Cuenta activa</label>
              <div>
                <label htmlFor="user-password" className="label flex items-center gap-2">
                  Contraseña {editingUser ? '(dejar vacío para no cambiar)' : '*'}
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="text-xs text-blue-500 hover:underline">{showPassword ? 'Ocultar' : 'Mostrar'}</button>
                </label>
                <input id="user-password" aria-invalid={!!formErrors.password} aria-describedby={formErrors.password ? "user-error-password" : undefined} autoComplete="new-password" type={showPassword ? 'text' : 'password'} value={formData.password} onChange={e => setFormData({...formData, password: e.target.value})} className="input mt-1" placeholder={editingUser ? '••••••••' : 'Mínimo 8 caracteres'} required={!editingUser} />
              </div>
              {formErrors.password && <p id="user-error-password" className="text-red-700 text-sm">{String(formErrors.password)}</p>}
              <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
                <button type="button" onClick={closeModal} className="btn-secondary" disabled={submitting}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={submitting}>{submitting ? 'Guardando...' : (editingUser ? 'Actualizar' : 'Crear')}</button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </div>
  )
}
