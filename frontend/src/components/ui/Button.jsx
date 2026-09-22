import Spinner from './Spinner'

const variants = {
  primary:   'ui-button--primary',
  secondary: 'ui-button--secondary',
  danger:    'ui-button--danger',
  ghost:     'ui-button--ghost',
  navy:      'ui-button--navy',
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
        ui-button inline-flex items-center justify-center gap-2 min-h-11 px-4 py-2.5 rounded-lg
        font-heading font-semibold text-sm
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
