import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Users, Search, Calendar } from 'lucide-react'
import { getPacientes } from '../api/pacientes'
import Spinner from '../components/ui/Spinner'

export default function PacientesPage() {
  const [pacientes, setPacientes] = useState([])
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState('')

  useEffect(() => {
    getPacientes({})
      .then(({ data }) => setPacientes(Array.isArray(data) ? data : data.results || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const filtrados = pacientes.filter(p =>
    `${p.nombres} ${p.apellidos} ${p.ci}`.toLowerCase().includes(busqueda.toLowerCase())
  )

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-heading font-bold text-navy text-3xl">Pacientes</h1>
          <p className="font-body text-slate-500 text-sm mt-1">{pacientes.length} registrado(s)</p>
        </div>
      </div>

      <div className="mb-4 relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
          placeholder="Buscar por nombre o CI..."
          className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 font-body text-sm
            focus:outline-none focus:ring-2 focus:ring-teal-med/40 focus:border-teal-med bg-white"
        />
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" color="navy" /></div>
      ) : filtrados.length === 0 ? (
        <div className="flex flex-col items-center py-16 gap-3 text-slate-400">
          <Users className="w-12 h-12 opacity-30" />
          <p className="font-body text-sm">No se encontraron pacientes</p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="text-xs font-heading font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                <th className="px-6 py-3 text-left">Nombre completo</th>
                <th className="px-6 py-3 text-left">CI</th>
                <th className="px-6 py-3 text-left">Nacimiento</th>
                <th className="px-6 py-3 text-left">Género</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filtrados.map((p, i) => (
                <motion.tr
                  key={p.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="hover:bg-slate-50 transition-colors"
                >
                  <td className="px-6 py-3 font-body text-sm text-navy font-semibold">
                    {p.nombres} {p.apellidos}
                  </td>
                  <td className="px-6 py-3 font-mono text-xs text-slate-500">{p.ci}</td>
                  <td className="px-6 py-3 font-mono text-xs text-slate-500">{p.fecha_nacimiento}</td>
                  <td className="px-6 py-3 font-body text-xs text-slate-500">{p.genero}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
