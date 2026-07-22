/**
 * Premium gradient button — replaces all inline `BTN` patterns.
 * Supports gradient backgrounds, glow effects, loading state, and disabled state.
 */
export function GradientBtn({ children, onClick, loading = false, disabled = false, variant = 'accent', size = 'md', style = {}, className = '', ...rest }) {
  const gradient = variant === 'accent' ? 'var(--gradient-accent)'
    : variant === 'success' ? 'var(--gradient-success)'
    : variant === 'danger' ? 'var(--gradient-danger)'
    : variant === 'warning' ? 'var(--gradient-warning)'
    : variant === 'info' ? 'var(--gradient-info)'
    : variant === 'ghost' ? 'none'
    : 'var(--gradient-accent)'

  const isGhost = variant === 'ghost'
  const padding = size === 'sm' ? '6px 14px' : size === 'lg' ? '10px 24px' : '8px 18px'
  const fontSize = size === 'sm' ? 'var(--font-size-xs)' : size === 'lg' ? 'var(--font-size-md)' : 'var(--font-size-sm)'

  return (
    <button
      className={className}
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        background: isGhost ? 'var(--surface3)' : gradient,
        border: isGhost ? '1px solid var(--border)' : 'none',
        borderRadius: 'var(--radius-md)',
        padding,
        fontSize,
        fontWeight: 'var(--font-weight-semibold)',
        fontFamily: 'var(--font)',
        color: isGhost ? 'var(--text-muted)' : '#fff',
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : loading ? 0.7 : 1,
        transition: 'all var(--transition-normal)',
        transform: 'translateY(0)',
        boxShadow: isGhost ? 'none' : '0 2px 12px rgba(79, 124, 255, 0.2)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        letterSpacing: '0.3px',
        outline: 'none',
        ...style,
      }}
      onMouseEnter={e => { if (!disabled && !loading) e.currentTarget.style.transform = 'translateY(-1px)' }}
      onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)' }}
      {...rest}
    >
      {loading && <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>}
      {children}
    </button>
  )
}
