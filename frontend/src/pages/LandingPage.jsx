import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Wind, ArrowRight, BrainCircuit, FileText, ShieldCheck,
  Activity, MapPin, ChevronDown,
} from 'lucide-react'
import ChestXray from '../components/landing/ChestXray'

// Ícono de pulmón (lucide no incluye uno) — stroke 2 para coherencia con el set
function LungIcon({ className = '' }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M12 4v8" />
      <path d="M9 8c0 2-1 3-1 3" />
      <path d="M15 8c0 2 1 3 1 3" />
      <path d="M6.5 11c-1.8 1.2-2.5 3.4-2.5 6 0 2 1 3 2.6 3 1.6 0 2.4-1 2.4-2.7V13c0-1.7-1.6-2.6-2.5-2z" />
      <path d="M17.5 11c1.8 1.2 2.5 3.4 2.5 6 0 2-1 3-2.6 3-1.6 0-2.4-1-2.4-2.7V13c0-1.7 1.6-2.6 2.5-2z" />
    </svg>
  )
}

const FEATURES = [
  {
    icon: BrainCircuit,
    title: 'Detección CNN en segundos',
    text: 'ResNet-50 con 50 capas residuales analiza cada radiografía en menos de 10 segundos.',
  },
  {
    icon: LungIcon,
    title: '13 patologías neumológicas',
    text: 'Neumonía, consolidaciones, nódulos, derrames y más, con probabilidades calibradas y mapas Grad-CAM.',
  },
  {
    icon: FileText,
    title: 'Informe preliminar automático',
    text: 'Borrador estructurado por secciones anatómicas listo para revisión y firma del médico radiólogo.',
  },
]

// Datos de ejemplo para el mockup de la sección demo
const DEMO_PATOLOGIAS = [
  { nombre: 'Neumonía', prob: 0.78, tag: 'CRÍTICO', cls: 'from-danger to-rose-400', tcls: 'text-danger' },
  { nombre: 'Consolidación', prob: 0.54, tag: 'MODERADO', cls: 'from-orange-400 to-orange-500', tcls: 'text-orange-500' },
  { nombre: 'Infiltrado', prob: 0.31, tag: 'LEVE', cls: 'from-warning to-amber-400', tcls: 'text-warning' },
  { nombre: 'Derrame pleural', prob: 0.12, tag: 'MARGINAL', cls: 'from-slate-400 to-slate-500', tcls: 'text-slate-400' },
]

export default function LandingPage() {
  const navigate = useNavigate()
  const irDemo = () => document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' })

  return (
    <div className="bg-scan-bg text-white font-body">
      {/* ════════ NAVBAR ════════ */}
      <header className="fixed top-0 inset-x-0 z-50 backdrop-blur-md bg-scan-bg/70 border-b border-white/5">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-teal-med/20 border border-teal-med/40 flex items-center justify-center">
              <Wind className="w-5 h-5 text-teal-med" />
            </div>
            <span className="font-heading font-extrabold tracking-tight text-lg">
              NEO <span className="text-teal-med">RX</span>
            </span>
          </div>
          <button
            onClick={() => navigate('/login')}
            className="font-heading font-semibold text-sm px-4 py-2 rounded-lg border border-white/15
              text-white/90 hover:bg-white/10 hover:border-white/30 transition-all cursor-pointer
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-med/60"
          >
            Iniciar sesión
          </button>
        </div>
      </header>

      {/* ════════ HERO ════════ */}
      <section className="relative min-h-screen flex items-center overflow-hidden pt-16">
        {/* Atmósfera de fondo */}
        <div className="absolute inset-0 bg-gradient-to-br from-navy via-scan-bg to-[#06101f]" />
        <div className="absolute inset-0 opacity-[0.06]" style={{
          backgroundImage: 'radial-gradient(circle, #38bdf8 1px, transparent 1px)',
          backgroundSize: '38px 38px',
        }} />
        <div className="absolute -top-40 -right-40 w-[42rem] h-[42rem] rounded-full bg-teal-med/10 blur-3xl" />

        <div className="relative z-10 max-w-6xl mx-auto px-6 grid lg:grid-cols-2 gap-12 items-center py-20">
          {/* Texto */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: 'easeOut' }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 mb-7">
              <MapPin className="w-3.5 h-3.5 text-teal-med" />
              <span className="font-mono text-[11px] text-white/60 tracking-wide">
                Centro Neo Rayos X Digital · La Paz, Bolivia
              </span>
            </div>

            <h1 className="font-heading font-extrabold text-4xl sm:text-5xl lg:text-[3.4rem] leading-[1.05] tracking-tight">
              Diagnóstico radiológico asistido por{' '}
              <span className="text-teal-med">inteligencia artificial</span>
            </h1>

            <p className="mt-6 text-white/55 text-lg leading-relaxed max-w-xl">
              Gestione pacientes, imágenes e informes radiológicos con apoyo
              de análisis experimental y revisión médica.
            </p>

            <div className="mt-9 flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => navigate('/login')}
                className="group inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl
                  bg-teal-med text-white font-heading font-semibold shadow-lg shadow-teal-med/25
                  hover:brightness-110 hover:scale-[1.02] active:scale-[0.99] transition-all cursor-pointer
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-med/60 focus-visible:ring-offset-2 focus-visible:ring-offset-scan-bg"
              >
                Ingresar al sistema
                <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
              </button>
              <button
                onClick={irDemo}
                className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl
                  border border-white/15 text-white/90 font-heading font-semibold
                  hover:bg-white/10 hover:border-white/30 transition-all cursor-pointer
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
              >
                Ver demo
              </button>
            </div>

            <div className="mt-10 flex flex-wrap gap-x-6 gap-y-2 font-mono text-[11px] text-white/35">
              {['ResNet-50 · 25.5M parámetros', 'Grad-CAM explicable', 'PadChest · NIH · RSNA · SIIM'].map((t) => (
                <span key={t} className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-teal-med" />{t}
                </span>
              ))}
            </div>
          </motion.div>

          {/* Radiografía animada */}
          <motion.div
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.9, ease: 'easeOut', delay: 0.15 }}
            className="relative hidden lg:block"
          >
            <div className="relative mx-auto max-w-md rounded-3xl border border-white/10 bg-white/[0.02] p-4 shadow-2xl">
              <ChestXray className="w-full" />
              <div className="absolute top-6 left-6 font-mono text-[10px] text-teal-med/70 tracking-widest">
                CHEST · PA
              </div>
              <motion.div
                className="absolute bottom-6 right-6 flex items-center gap-1.5 font-mono text-[10px] text-white/50"
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ repeat: Infinity, duration: 1.8 }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-success" /> ANALIZANDO
              </motion.div>
            </div>
          </motion.div>
        </div>

        {/* Indicador de scroll */}
        <button
          onClick={irDemo}
          aria-label="Desplazarse a la demostración"
          className="absolute bottom-6 left-1/2 -translate-x-1/2 text-white/30 hover:text-white/70 transition-colors cursor-pointer"
        >
          <motion.div animate={{ y: [0, 6, 0] }} transition={{ repeat: Infinity, duration: 1.6 }}>
            <ChevronDown className="w-6 h-6" />
          </motion.div>
        </button>
      </section>

      {/* ════════ CARACTERÍSTICAS ════════ */}
      <section className="relative max-w-6xl mx-auto px-6 py-24">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <p className="font-mono text-xs text-teal-med tracking-[0.2em] uppercase mb-3">Capacidades</p>
          <h2 className="font-heading font-bold text-3xl sm:text-4xl tracking-tight">
            Apoyo diagnóstico de extremo a extremo
          </h2>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {FEATURES.map(({ icon: Icon, title, text }, i) => (
            <motion.div
              key={title}
              initial={{ opacity: 0, y: 22 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              whileHover={{ y: -4 }}
              className="rounded-2xl border border-white/10 bg-white/[0.03] p-7
                hover:border-teal-med/40 hover:bg-white/[0.05] transition-colors"
            >
              <div className="w-12 h-12 rounded-xl bg-teal-med/15 border border-teal-med/30 flex items-center justify-center mb-5">
                <Icon className="w-6 h-6 text-teal-med" />
              </div>
              <h3 className="font-heading font-bold text-lg mb-2">{title}</h3>
              <p className="text-white/50 text-sm leading-relaxed">{text}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ════════ DEMO ════════ */}
      <section id="demo" className="bg-[#F0F4F8] text-navy py-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <p className="font-mono text-xs text-teal-med tracking-[0.2em] uppercase mb-3">Demostración</p>
            <h2 className="font-heading font-bold text-3xl sm:text-4xl tracking-tight">
              Así funciona el análisis
            </h2>
            <p className="mt-4 text-slate-500 text-lg">
              Grad-CAM muestra exactamente qué regiones activaron la red.
            </p>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.6 }}
            className="grid lg:grid-cols-2 gap-6 rounded-3xl border border-slate-200 bg-white shadow-[0_8px_40px_rgba(15,41,66,0.08)] p-6"
          >
            {/* Visor radiografía */}
            <div className="rounded-2xl bg-scan-bg border border-[#1e3a5f] p-5 flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <span className="font-mono text-[11px] text-white/50 tracking-widest">RADIOGRAFÍA · PA</span>
                <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-success/15 text-success text-[10px] font-mono">
                  <Activity className="w-3 h-3" /> Nitidez OK
                </span>
              </div>
              <div className="flex-1 flex items-center justify-center">
                <ChestXray className="w-full max-w-[280px]" />
              </div>
              <div className="mt-4 flex items-center justify-between">
                <span className="font-mono text-[10px] text-white/40">Grad-CAM · layer4</span>
                <div className="h-2.5 w-40 rounded-full" style={{
                  background: 'linear-gradient(to right,#000080,#0000ff,#00ffff,#00ff00,#ffff00,#ff8000,#ff0000)',
                }} />
              </div>
            </div>

            {/* Panel resultados */}
            <div className="flex flex-col gap-4">
              <div className="rounded-2xl border border-slate-200 p-5">
                <div className="flex items-baseline justify-between mb-3">
                  <h3 className="font-heading font-bold text-base">Confianza diagnóstica</h3>
                  <span className="font-mono font-bold text-2xl text-danger">78%</span>
                </div>
                <div className="w-full h-5 bg-slate-100 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-danger to-rose-400"
                    initial={{ width: 0 }}
                    whileInView={{ width: '78%' }}
                    viewport={{ once: true }}
                    transition={{ duration: 1.2, ease: 'easeOut' }}
                  />
                </div>
                <p className="mt-3 text-sm text-slate-600">
                  Hallazgo principal: <span className="font-heading font-bold text-danger">Neumonía</span>
                </p>
              </div>

              <div className="rounded-2xl border border-slate-200 p-5">
                <h3 className="font-heading font-bold text-base mb-4">Hallazgos detectados</h3>
                <div className="space-y-3">
                  {DEMO_PATOLOGIAS.map(({ nombre, prob, tag, cls, tcls }, i) => (
                    <div key={nombre}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-semibold text-navy flex-1">{nombre}</span>
                        <span className={`text-[10px] font-mono font-bold ${tcls}`}>{tag}</span>
                        <span className="font-mono text-sm font-bold text-slate-700 w-10 text-right">
                          {Math.round(prob * 100)}%
                        </span>
                      </div>
                      <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                        <motion.div
                          className={`h-full rounded-full bg-gradient-to-r ${cls}`}
                          initial={{ width: 0 }}
                          whileInView={{ width: `${prob * 100}%` }}
                          viewport={{ once: true }}
                          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 + i * 0.08 }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>

          <div className="text-center mt-10">
            <button
              onClick={() => navigate('/login')}
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-navy text-white
                font-heading font-semibold shadow-lg shadow-navy/20 hover:brightness-110 hover:scale-[1.02]
                transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy/50"
            >
              Ingresar al sistema <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* ════════ FOOTER ════════ */}
      <footer className="bg-scan-bg border-t border-white/5 py-10">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-teal-med/20 border border-teal-med/40 flex items-center justify-center">
              <Wind className="w-4 h-4 text-teal-med" />
            </div>
            <span className="font-heading font-bold tracking-tight">NEO <span className="text-teal-med">RX</span></span>
          </div>
          <div className="flex items-center gap-2 text-white/40 text-xs font-body text-center sm:text-right">
            <ShieldCheck className="w-4 h-4 text-teal-med/60 hidden sm:block" />
            <p>
              Universidad Privada del Valle · Facultad de Informática y Electrónica<br />
              Proyecto de Grado 2026 · Javier Limber Morales Merlo
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
