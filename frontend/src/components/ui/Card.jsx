export default function Card({ children, className = '', dark = false }) {
  const base = dark
    ? 'bg-surface border border-white/10 rounded-xl shadow-lg'
    : 'bg-white border border-slate-200 rounded-xl shadow-sm'
  return <div className={`${base} ${className}`}>{children}</div>
}
