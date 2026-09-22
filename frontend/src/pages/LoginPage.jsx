import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Wind, Eye, EyeOff, LogIn } from 'lucide-react'
import { useAuth } from '../context/useAuth'
import PasswordResetDialog from '../components/auth/PasswordResetDialog'
import ThemeSwitcher from '../components/layout/ThemeSwitcher'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [remember, setRemember] = useState(false)
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [resetOpen, setResetOpen] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(form.username, form.password, remember)
      navigate('/dashboard')
    } catch {
      setError('Credenciales incorrectas. Verifica tu usuario o correo y contraseña.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page min-h-screen flex relative">
      <div className="public-theme-control"><ThemeSwitcher /></div>
      {/* Mitad izquierda — Fondo X-ray */}
      <div className="auth-visual hidden lg:flex flex-1 relative overflow-hidden bg-scan-bg">
        {/* Gradient overlay */}
        <div className="auth-visual-backdrop absolute inset-0 bg-gradient-to-br from-navy via-scan-bg to-surface" />

        {/* Patrón de puntos decorativo */}
        <div className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: 'radial-gradient(circle, #0EA5E9 1px, transparent 1px)',
            backgroundSize: '32px 32px'
          }}
        />

        {/* Contenido central */}
        <div className="relative z-10 flex flex-col items-center justify-center w-full px-12 text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
          >
            {/* Logo grande decorativo */}
            <div className="flex items-center gap-4 justify-center mb-6">
              <div className="w-16 h-16 rounded-2xl bg-teal-med/20 border border-teal-med/40 flex items-center justify-center">
                <Wind className="w-9 h-9 text-teal-med" />
              </div>
            </div>
            <h1 className="font-heading font-extrabold text-white text-6xl tracking-tight leading-none">
              NEO <span className="text-teal-med">RX</span>
            </h1>
            <p className="font-body text-white/60 text-lg mt-4 max-w-sm">
              Diagnóstico radiológico asistido por inteligencia artificial
            </p>
            <div className="mt-8 flex flex-col gap-2 text-left max-w-xs mx-auto">
              {[
                'ResNet-50 · 25.5M parámetros',
                'Acceso seguro según el rol del usuario',
                'Grad-CAM para explicabilidad',
                'PadChest · NIH · RSNA · SIIM · VinBigData',
              ].map((line) => (
                <div key={line} className="flex items-center gap-2 font-mono text-xs text-white/40">
                  <span className="w-1.5 h-1.5 rounded-full bg-teal-med flex-shrink-0" />
                  {line}
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div
            className="absolute bottom-8 font-body text-white/25 text-xs"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1 }}
          >
            Universidad Privada del Valle · La Paz, Bolivia · 2026
          </motion.div>
        </div>
      </div>

      {/* Mitad derecha — Formulario */}
      <div className="auth-panel flex-1 flex items-center justify-center px-8 bg-white">
        <motion.div
          className="w-full max-w-sm"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
        >
          {/* Logo móvil */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-10 h-10 rounded-xl bg-navy flex items-center justify-center">
              <Wind className="w-5 h-5 text-teal-med" />
            </div>
            <span className="font-heading font-bold text-navy text-xl">NEO RX</span>
          </div>

          <h2 className="font-heading font-bold text-navy text-3xl mb-1">Iniciar sesión</h2>
          <p className="font-body text-slate-500 text-sm mb-8">
            Centro Neo Rayos X Digital
          </p>

          {error && (
            <div className="mb-4 p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger text-sm font-body">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="font-body text-sm font-semibold text-navy block mb-1.5" htmlFor="username">
                Usuario o correo electrónico
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                value={form.username}
                onChange={(e) => setForm(f => ({ ...f, username: e.target.value }))}
                className="w-full px-4 py-3 rounded-xl border border-slate-200 font-body text-sm text-navy
                  focus:outline-none focus:ring-2 focus:ring-teal-med/40 focus:border-teal-med
                  transition-all placeholder:text-slate-400"
                placeholder="nombre.usuario o correo@dominio.com"
                required
              />
            </div>

            <div>
              <label className="font-body text-sm font-semibold text-navy block mb-1.5" htmlFor="password">
                Contraseña
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPass ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={form.password}
                  onChange={(e) => setForm(f => ({ ...f, password: e.target.value }))}
                  className="w-full px-4 py-3 pr-11 rounded-xl border border-slate-200 font-body text-sm text-navy
                    focus:outline-none focus:ring-2 focus:ring-teal-med/40 focus:border-teal-med
                    transition-all placeholder:text-slate-400"
                  placeholder="••••••••"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPass(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-navy cursor-pointer"
                  aria-label={showPass ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between gap-3 text-sm">
              <label className="flex items-center gap-2 min-h-11"><input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} />Recuérdame</label>
              <button type="button" onClick={() => setResetOpen(true)} className="text-sky-800 underline underline-offset-4">¿Olvidaste tu contraseña?</button>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="ui-button ui-button--primary w-full flex items-center justify-center gap-2 py-3 rounded-xl
                text-white font-heading font-semibold text-base disabled:opacity-60 cursor-pointer
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy/60 mt-2"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <LogIn className="w-4 h-4" />
              )}
              {loading ? 'Verificando...' : 'Ingresar'}
            </button>
          </form>

          <p className="font-body text-center text-xs text-slate-400 mt-8">
            Universidad Privada del Valle · 2026
          </p>
        </motion.div>
      </div>
      {resetOpen && <PasswordResetDialog onClose={() => setResetOpen(false)}/>}
    </div>
  )
}
