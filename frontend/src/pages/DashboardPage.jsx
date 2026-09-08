import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ScanLine, Clock, FileText, Plus, ChevronRight } from 'lucide-react'
import { getEstudios } from '../api/pacientes'
import { useToast } from '../context/ToastContext'
import Spinner from '../components/ui/Spinner'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'

const ESTADO_BADGE = {
  pendiente: 'info',
  en_proceso: 'moderado',
  completado: 'ok',
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [estudios, setEstudios] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getEstudios({})
      .then(({ data }) => setEstudios(Array.isArray(data) ? data : data.results || []))
      .catch((e) => { if (!e.response) toast.red() })
      .finally(() => setLoading(false))
  }, [toast])

  const hoy = new Date().toISOString().split('T')[0]
  const estudiosHoy = estudios.filter(e => e.created_at?.startsWith(hoy)).length
  const pendientes = estudios.filter(e => e.estado === 'pendiente').length

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading font-bold text-navy text-3xl">Dashboard</h1>
          <p className="font-body text-slate-500 text-sm mt-1">Centro Neo Rayos X Digital</p>
        </div>
        <Button onClick={() => navigate('/escaneo')} className="gap-2">
          <Plus className="w-4 h-4" /> Nuevo Escaneo
        </Button>
      </div>

      {/* Métricas */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {[
          { icon: ScanLine,  label: 'Estudios hoy',           val: estudiosHoy, color: 'text-teal-med', bg: 'bg-teal-med/10' },
          { icon: Clock,     label: 'Pendientes de informe',  val: pendientes,  color: 'text-warning',  bg: 'bg-warning/10' },
          { icon: FileText,  label: 'Total estudios',         val: estudios.length, color: 'text-navy', bg: 'bg-navy/10' },
        ].map(({ icon: Icon, label, val, color, bg }, i) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex items-center gap-4"
          >
            <div className={`w-12 h-12 rounded-xl ${bg} flex items-center justify-center flex-shrink-0`}>
              <Icon className={`w-6 h-6 ${color}`} />
            </div>
            <div>
              <p className="font-mono font-bold text-navy text-2xl">{val}</p>
              <p className="font-body text-slate-500 text-sm">{label}</p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Tabla de estudios recientes */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100">
          <h2 className="font-heading font-bold text-navy text-base">Estudios recientes</h2>
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <Spinner size="lg" color="navy" />
          </div>
        ) : estudios.length === 0 ? (
          <div className="flex flex-col items-center py-16 gap-3 text-slate-400">
            <ScanLine className="w-12 h-12 opacity-30" />
            <p className="font-body text-sm">No hay estudios aún</p>
            <Button variant="secondary" onClick={() => navigate('/escaneo')}>
              Crear primer escaneo
            </Button>
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
                    <td className="px-6 py-3 font-body text-sm text-navy font-medium">
                      {est.paciente_nombre || `Paciente #${est.paciente}`}
                    </td>
                    <td className="px-6 py-3 font-mono text-xs text-slate-500">{est.fecha}</td>
                    <td className="px-6 py-3 font-body text-sm text-slate-600">{est.tipo_estudio}</td>
                    <td className="px-6 py-3">
                      <Badge variant={ESTADO_BADGE[est.estado] || 'info'}>{est.estado}</Badge>
                    </td>
                    <td className="px-6 py-3">
                      <button
                        onClick={() => navigate('/escaneo')}
                        className="flex items-center gap-1 text-teal-med font-body text-xs hover:underline cursor-pointer"
                      >
                        Ver <ChevronRight className="w-3 h-3" />
                      </button>
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
