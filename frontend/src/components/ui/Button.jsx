import Spinner from './Spinner'

const variants = {
  primary:   'bg-teal-med hover:bg-sky-400 text-white shadow-md hover:shadow-teal-med/30',
  secondary: 'bg-white hover:bg-slate-50 text-navy border border-slate-200 shadow-sm',
  danger:    'bg-danger hover:bg-red-500 text-white shadow-md',
  ghost:     'bg-transparent hover:bg-white/10 text-white/80 hover:text-white',
  navy:      'bg-navy hover:bg-navy/90 text-white shadow-md',
}

export default function Button({
  children, variant = 'primary', loading = false,
  disabled = false, className = '', ...props
}) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`
        inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg
        font-heading font-semibold text-sm transition-all duration-200
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-med/60
        disabled:opacity-50 disabled:cursor-not-allowed
        cursor-pointer
        ${variants[variant]} ${className}
      `}
    >
      {loading && <Spinner size="sm" color={variant === 'secondary' ? 'navy' : 'white'} />}
      {children}
    </button>
  )
}
