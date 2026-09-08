export default function Spinner({ size = 'md', color = 'teal' }) {
  const sizes = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10', xl: 'w-16 h-16' }
  const colors = {
    teal:  'border-teal-med/30 border-t-teal-med',
    white: 'border-white/30 border-t-white',
    navy:  'border-navy/30 border-t-navy',
  }
  return (
    <div
      className={`${sizes[size]} rounded-full border-2 animate-spin ${colors[color]}`}
      role="status"
      aria-label="Cargando"
    />
  )
}
