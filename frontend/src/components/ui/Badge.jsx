const variants = {
  critico:  'bg-danger/15 text-danger border border-danger/30',
  moderado: 'bg-orange-500/15 text-orange-500 border border-orange-500/30',
  leve:     'bg-warning/15 text-warning border border-warning/30',
  marginal: 'bg-slate-500/15 text-slate-500 border border-slate-500/30',
  ok:       'bg-success/15 text-success border border-success/30',
  info:     'bg-teal-med/15 text-teal-med border border-teal-med/30',
}

export default function Badge({ variant = 'info', children }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-mono font-medium ${variants[variant]}`}>
      {children}
    </span>
  )
}
