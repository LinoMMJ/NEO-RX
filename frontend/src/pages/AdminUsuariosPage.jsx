import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Users, Plus, Search, Filter, Edit, Trash2, Lock, AlertCircle,
  ChevronDown, ChevronUp, Eye, Mail, Shield, UserCheck, UserX
} from 'lucide-react'
import { api } from '../../api'
import { ToastContainer } from '../../context/ToastContext'

const ROL_LABELS = {
  medico: 'Médico Radiólogo',
  tecnico: 'Técnico Radiólogo',
  administrador: 'Administrador',
}

const ROL_COLORS = {
  medico: 'bg-emerald-100 text-emerald-700',
  tecnico: 'bg-blue-100 text-blue-700',
  administrador: 'bg-violet-100 text-violet-700',
}

const ROL_ICONS = {
  medico: Shield,
  tecnico: Mail,
  administrador: UserCheck,
}

export default function AdminUsuariosPage() {
  const [usuarios, setUsuarios] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(10)
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [rolFilter, setRolFilter] = useState('')
  const [activoFilter, setActivoFilter] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [formData, setFormData] = useState({ username: '', email: '', first_name: '', last_name: '', rol: 'tecnico', password: '' })
  const [submitting, setSubmitting] = useState(false)
  const [sortField, setSortField] = useState('date_joined')
  const [sortDir, setSortDir] = useState('desc')
  const [showPassword, setShowPassword] = useState(false)
  const [resetPasswordUser, setResetPasswordUser] = useState(null)

  const fetchUsuarios = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        page,
        page_size: pageSize,
        ordering: `${sortDir === 'desc' ? '-' : ''}${sortField}`,
      })
      if (search) params.append('search', search)
      if (rolFilter) params.append('rol', rolFilter)
      if (activoFilter) params.append('is_active', activoFilter)

      const res = await api.get(`/admin/users/?${params.toString()}`)
      setUsuarios(res.data.results || res.data)
      setTotal(res.data.count || res.data.length)
    } catch (err) {
      setError('Error al cargar usuarios')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchUsuarios() }, [page, search, rolFilter, activoFilter, sortField, sortDir])

  const handleSort = (field) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortField(field); setSortDir('asc') }
  }

  const openCreateModal = () => {
    setEditingUser(null)
    setFormData({ username: '', email: '', first_name: '', last_name: '', rol: 'tecnico', password: '' })
    setShowModal(true)
  }

  const openEditModal = (user) => {
    setEditingUser(user)
    setFormData({ username: user.username, email: user.email, first_name: user.first_name, last_name: user.last_name, rol: user.rol, password: '' })
    setShowModal(true)
  }

  const closeModal = () => { setShowModal(false); setEditingUser(null) }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      const payload = { ...formData }
      if (!payload.password) delete payload.password
      if (editingUser) {
        await api.put(`/admin/users/${editingUser.id}/`, payload)
      } else {
        await api.post('/admin/users/', payload)
      }
      closeModal()
      fetchUsuarios()
    } catch (err) {
      console.error(err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleActive = async (user) => {
    try {
      await api.post(`/admin/users/${user.id}/toggle_active/`)
      fetchUsuarios()
    } catch (err) { console.error(err) }
  }

  const handleResetPassword = async (user) => {
    setResetPasswordUser(user)
    try {
      const res = await api.post(`/admin/users/${user.id}/reset_password/`)
      alert(`Password temporal para ${user.username}:\n\n${res.data.temporary_password}\n\nCópiala ahora, no se mostrará de nuevo.`)
    } catch (err) { console.error(err) }
    setResetPasswordUser(null)
  }

  return (
    <div className="p-6 space-y-6">
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
              placeholder="Buscar (nombre, email, username)..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
              className="input w-full pl-10 pr-4 py-2"
            />
          </div>
          <select
            value={rolFilter}
            onChange={e => { setRolFilter(e.target.value); setPage(1) }}
            className="input py-2"
          >
            <option value="">Todos los roles</option>
            <option value="medico">Médico Radiólogo</option>
            <option value="tecnico">Técnico Radiólogo</option>
            <option value="administrador">Administrador</option>
          </select>
          <select
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
            <select value={pageSize} onChange={e => { pageSize = Number(e.target.value); setPage(1) }} className="input py-1 w-20">
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
            <table className="w-full">
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
                    <th key={col.key} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100"
                        onClick={() => handleSort(col.key === 'username' ? 'username' : col.key === 'email' ? 'email' : col.key === 'first_name' ? 'first_name' : col.key === 'date_joined' ? 'date_joined' : null)}>
                      <div className="flex items-center gap-1">
                        {col.label}
                        {sortField === (col.key === 'username' ? 'username' : col.key === 'email' ? 'email' : col.key === 'first_name' ? 'first_name' : col.key === 'date_joined' ? 'date_joined' : null) && (
                          sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {usuarios.map((user, i) => (
                  <motion.tr key={user.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                    <td className="px-4 py-3">
                      <div className="font-mono font-medium text-navy">{user.username}</td>
                    <td className="px-4 py-3 font-body text-sm text-slate-600">{user.email || '—'}</td>
                    <td className="px-4 py-3 font-body text-sm text-slate-700">{user.get_full_name() || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${ROL_COLORS[user.rol]}`}>
                        <ROL_ICONS[user.rol] className="w-3 h-3" />
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
                        <button onClick={() => openEditModal(user)} className="p-2 text-slate-400 hover:text-navy hover:bg-slate-100 rounded-lg transition" title="Editar"><Edit className="w-4 h-4" /></button>
                        <button onClick={() => handleToggleActive(user)} className={`p-2 ${user.is_active ? 'text-orange-400 hover:text-orange-600' : 'text-emerald-400 hover:text-emerald-600'} hover:bg-slate-100 rounded-lg transition`} title={user.is_active ? 'Desactivar' : 'Activar'}>{user.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}</button>
                        <button onClick={() => handleResetPassword(user)} disabled={resetPasswordUser === user.id} className={`p-2 ${resetPasswordUser === user.id ? 'text-slate-300 cursor-not-allowed' : 'text-blue-400 hover:text-blue-600'} hover:bg-slate-100 rounded-lg transition`} title="Reset password"><Lock className="w-4 h-4" /></button>
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
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="bg-white rounded-2xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-slate-200 flex items-center justify-between">
              <h2 className="font-heading text-xl font-bold text-navy">{editingUser ? 'Editar usuario' : 'Nuevo usuario'}</h2>
              <button onClick={closeModal} className="p-2 text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Usuario *</label>
                  <input type="text" value={formData.username} onChange={e => setFormData({...formData, username: e.target.value})} className="input mt-1" required disabled={!!editingUser} />
                </div>
                <div>
                  <label className="label">Email</label>
                  <input type="email" value={formData.email} onChange={e => setFormData({...formData, email: e.target.value})} className="input mt-1" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Nombres</label>
                  <input type="text" value={formData.first_name} onChange={e => setFormData({...formData, first_name: e.target.value})} className="input mt-1" />
                </div>
                <div>
                  <label className="label">Apellidos</label>
                  <input type="text" value={formData.last_name} onChange={e => setFormData({...formData, last_name: e.target.value})} className="input mt-1" />
                </div>
              </div>
              <div>
                <label className="label">Rol *</label>
                <select value={formData.rol} onChange={e => setFormData({...formData, rol: e.target.value})} className="input mt-1">
                  <option value="tecnico">Técnico Radiólogo</option>
                  <option value="medico">Médico Radiólogo</option>
                  <option value="administrador">Administrador</option>
                </select>
              </div>
              <div>
                <label className="label flex items-center gap-2">
                  Password {editingUser ? '(dejar vacío para no cambiar)' : '*'}
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="text-xs text-blue-500 hover:underline">{showPassword ? 'Ocultar' : 'Mostrar'}</button>
                </label>
                <input type={showPassword ? 'text' : 'password'} value={formData.password} onChange={e => setFormData({...formData, password: e.target.value})} className="input mt-1" placeholder={editingUser ? '••••••••' : 'Mínimo 8 caracteres'} required={!editingUser} />
              </div>
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