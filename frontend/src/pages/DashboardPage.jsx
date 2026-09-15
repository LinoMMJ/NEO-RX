import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ScanLine, Clock, FileText, Plus, ChevronRight,
  TrendingUp, Activity, BarChart3, Users, AlertCircle
} from 'lucide-react'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, PieChart, Pie, Cell
} from 'recharts'
import { getEstudios } from '../api/pacientes'
import { api } from '../api'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import Spinner from '../components/ui/Spinner'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'

const ESTADO_BADGE = {
  pendiente: 'info',
  en_proceso: 'moderado',
  completado: 'ok',
}

const COLORS = ['#0d9488', '#f59e0b', '#3b82f6', '#8b5cf6', '#ef4444', '#06b6d4', '#84cc16', '#f97316']

export default function DashboardPage() {
  const navigate = useNavigate()
  const { rol } = useAuth()
  const toast = useToast()
  const [estudios, setEstudios] = useState([])
  const [loading, setLoading] = useState(true)
  const [metrics, setMetrics] = useState(null)
  const [metricsLoading, setMetricsLoading] = useState(true)

  useEffect(() => {
    getEstudios({})
      .then(({ data }) => setEstudios(Array.isArray(data) ? data : data.results || []))
      .catch((e) => { if (!e.response) toast.red() })
      .finally(() => setLoading(false))
  }, [toast])

  useEffect(() => {
    api.get('/metrics/operacionales/', { params: { dias: 30 } })
      .then(res => setMetrics(res.data))
      .catch(err => console.error('Error cargando métricas:', err))
      .finally(() => setMetricsLoading(false))
  }, [])

  const hoy = new Date().toISOString().split('T')[0]
  const estudiosHoy = estudios.filter(e => e.created_at?.startsWith(hoy)).length
  const pendientes = estudios.filter(e => e.estado === 'pendiente').length

  const isAdmin = rol === 'administrador'
  const isMedico = rol === 'medico'

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="font-heading font-bold text-navy text-3xl">Dashboard Operativo</h1>
          <p className="font-body text-slate-500 text-sm mt-1">Centro Neo Rayos X Digital — Métricas en tiempo real</p>
        </div>
        <Button onClick={() => navigate('/escaneo')} className="gap-2">
          <Plus className="w-4 h-4" /> Nuevo Escaneo
        </Button>
      </div>

      {/* Métricas principales (KPIs) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { icon: ScanLine,  label: 'Estudios hoy',           val: metrics?.estudios_por_dia?.find(d => d.fecha === new Date().toISOString().split('T')[0])?.total || estudiosHoy, color: 'text-teal-med', bg: 'bg-teal-med/10', iconColor: 'teal-med' },
          { icon: Clock,     label: 'Pendientes de informe',  val: metrics?.completitud?.pendientes || pendientes,  color: 'text-warning',  bg: 'bg-warning/10', iconColor: 'warning' },
          { icon: FileText,  label: 'Total (30d)',            val: metrics?.completitud?.total || estudios.length, color: 'text-navy', bg: 'bg-navy/10', iconColor: 'navy' },
          { icon: TrendingUp, label: '% Completados',          val: metrics?.completitud?.porcentaje_completados ? `${metrics.completitud.porcentaje_completados}%` : '—', color: 'text-emerald-600', bg: 'bg-emerald-100', iconColor: 'emerald-600' },
        ].map(({ icon: Icon, label, val, color, bg, iconColor }, i) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex items-center gap-4"
          >
            <div className={`w-12 h-12 rounded-xl ${bg} flex items-center justify-center flex-shrink-0`}>
              <Icon className={`w-6 h-6 text-${iconColor}`} />
            </div>
            <div>
              <p className="font-mono font-bold text-navy text-2xl">{val}</p>
              <p className="font-body text-slate-500 text-sm">{label}</p>
            </div>
          </motion.div>
        ))}

      {/* Latencia diagnóstico */}
      {metrics && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm mb-8"
        >
          <h3 className="font-heading font-bold text-navy text-base mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-orange-500" />
            Latencia diagnóstica (horas) — Estudios con informe firmado
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            {[
              { label: 'Promedio', val: metrics.latencia_diagnostico?.promedio || 0, color: 'text-navy' },
              { label: 'P50 (mediana)', val: metrics.latencia_diagnostico?.p50 || 0, color: 'text-blue-600' },
              { label: 'P95', val: metrics.latencia_diagnostico?.p95 || 0, color: 'text-orange-500' },
              { label: 'P99', val: metrics.latencia_diagnostico?.p99 || 0, color: 'text-red-500' },
            ].map(({ label, val, color }, i) => (
              <motion.div key={label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className="bg-slate-50 rounded-xl p-4 text-center">
                <p className="font-mono font-bold text-2xl {color}">{val}h</p>
                <p className="font-body text-xs text-slate-500 mt-1">{label}</p>
              </motion.div>
            ))}
          </div>
          <p className="font-body text-xs text-slate-400 mt-3 text-center">
            Basado en {metrics.latencia_diagnostico?.muestras || 0} estudios firmados en 30 días
          </p>
        </motion.div>
      )}

      {/* Gráficos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Estudios por día (últimos 30 días) */}
        {metrics && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm"
          >
            <h3 className="font-heading font-bold text-navy text-base mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-teal-med" />
              Estudios por día (últimos 30 días)
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={metrics.estudios_por_dia}>
                <defs>
                  <linearGradient id="colorEstudios" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0d9488" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#0d9488" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="fecha" tickFormatter={d => new Date(d).toLocaleDateString('es-BO', { day: '2-digit', month: '2-digit' })} tick={{ fontSize: 10, fill: '#64748b' }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip
                  formatter={v => [v, 'estudios']}
                  contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
                />
                <Area type="monotone" dataKey="total" stroke="#0d9488" strokeWidth={2} fillOpacity={1} fill="url(#colorEstudios)" />
              </AreaChart>
            </ResponsiveContainer>
          </motion.div>
        )}

        {/* Heatmap horario */}
        {metrics && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm"
          >
            <h3 className="font-heading font-bold text-navy text-base mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-orange-500" />
              Distribución horaria de estudios (24h)
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={metrics.estudios_por_hora} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#64748b' }} />
                <YAxis dataKey="hora" type="category" tick={{ fontSize: 10, fill: '#64748b' }} width={50} tickFormatter={h => `${h}:00`} />
                <Tooltip formatter={v => [v, 'estudios']} contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }} />
                <Bar dataKey="total" fill="#f59e0b" radius={[0, 4, 4, 0]} maxBarSize={30} />
              </BarChart>
            </ResponsiveContainer>
          </motion.div>
        )}

        {/* Top patologías */}
        {metrics && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm lg:col-span-2"
          >
            <h3 className="font-heading font-bold text-navy text-base mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-emerald-600" />
              Top 10 patologías detectadas (últimos 30 días)
            </h3>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={metrics.top_patologias} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#64748b' }} />
                <YAxis dataKey="nombre" type="category" tick={{ fontSize: 11, fill: '#334155' }} width={180} />
                <Tooltip formatter={v => [v, 'detecciones']} contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }} />
                <Bar dataKey="conteo" fill="#10b981" radius={[0, 4, 4, 0]} maxBarSize={30}>
                  {metrics.top_patologias.map((_, i) => <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </motion.div>
        )}

        {/* Completitud - Pie chart */}
        {metrics && isAdmin && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
            className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm"
          >
            <h3 className="font-heading font-bold text-navy text-base mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-600" />
              Completitud de informes (30 días)
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={[
                    { name: 'Completados', value: metrics.completitud?.completados || 0 },
                    { name: 'Pendientes', value: metrics.completitud?.pendientes || 0 },
                  ]}
                  cx="50%" cy="50%" innerRadius={60} outerRadius={100}
                  paddingAngle={2} dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
                  labelLine={false}
                >
                  <Cell fill="#10b981" />
                  <Cell fill="#f59e0b" />
                </Pie>
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </motion.div>
        )}

        {/* Usuarios por rol */}
        {metrics && isAdmin && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
            className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm"
          >
            <h3 className="font-heading font-bold text-navy text-base mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-violet-600" />
              Usuarios por rol
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={metrics.usuarios_por_rol || []}
                  cx="50%" cy="50%" innerRadius={60} outerRadius={100}
                  paddingAngle={2} dataKey="total" nameKey="rol"
                  label={({ rol, percent }) => `${rol} ${(percent * 100).toFixed(1)}%`}
                  labelLine={false}
                >
                  {COLORS.map((c, i) => <Cell key={i} fill={c} />)}
                </Pie>
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </motion.div>
        )}

      </div>

      {/* Tabla de estudios recientes */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="font-heading font-bold text-navy text-base">Estudios recientes</h2>
          <Badge variant="info">{estudios.length} total</Badge>
        </div>

        {loading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" color="navy" /></div>
        ) : estudios.length === 0 ? (
          <div className="flex flex-col items-center py-16 gap-3 text-slate-400">
            <ScanLine className="w-12 h-12 opacity-30" />
            <p className="font-body text-sm">No hay estudios aún</p>
            <Button variant="secondary" onClick={() => navigate('/escaneo')}>Crear primer escaneo</Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs font-heading font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                  <th className="px-6 py-3 text-left">Paciente</th>
                  <th className="px-6 py-3 text-left">Fecha</th>
                  <th className="px-6 py-3 text-left">Tipo estudio</th>
                  <th className="px-6 py-3 text-left">Estado</th>
                  <th className="px-6 py-3 text-left">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {estudios.slice(0, 10).map((est) => (
                  <tr key={est.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-3 font-body text-sm text-navy font-medium">{est.paciente_nombre || `Paciente #${est.paciente}`}</td>
                    <td className="px-6 py-3 font-mono text-xs text-slate-500">{est.fecha}</td>
                    <td className="px-6 py-3 font-body text-sm text-slate-600">{est.tipo_estudio}</td>
                    <td className="px-6 py-3"><Badge variant={ESTADO_BADGE[est.estado] || 'info'}>{est.estado}</Badge></td>
                    <td className="px-6 py-3">
                      <button onClick={() => navigate('/escaneo')} className="flex items-center gap-1 text-teal-med font-body text-xs hover:underline cursor-pointer">Ver <ChevronRight className="w-3 h-3" /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}