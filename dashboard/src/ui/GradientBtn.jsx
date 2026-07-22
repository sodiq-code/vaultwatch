/**
 * GradientBtn — Premium gradient button with glow, loading state, and variants.
 */

const VARIANT_MAP = {
  primary: {
    bg: 'var(--gradient-accent)',
    hoverBg: 'linear-gradient(135deg, #00d4ff, #8b5cf6)',
    color: '#fff',
    glow: 'var(--shadow-glow)',
  },
  secondary: {
    bg: 'var(--gradient-accent2)',
    hoverBg: 'linear-gradient(135deg, #8b5cf6, #c084fc)',
    color: '#fff',
    glow: 'var(--shadow-glow2)',
  },
  success: {
    bg: 'var(--gradient-success)',
    hoverBg: 'linear-gradient(135deg, #00e68a, #00cc7a)',
    color: '#fff',
    glow: 'var(--shadow-glow-success)',
  },
  danger: {
    bg: 'var(--gradient-danger)',
    hoverBg: 'linear-gradient(135deg, #ff3b5c, #e6194b)',
    color: '#fff',
    glow: 'var(--shadow-glow-danger)',
  },
  warning: {
    bg: 'var(--gradient-warning)',
    hoverBg: 'linear-gradient(135deg, #ffb020, #ff8c00)',
    color: '#fff',
    glow: 'var(--shadow-glow-warning)',
  },
  ghost: {
    bg: 'transparent',
    hoverBg: 'rgba(0, 212, 255, 0.08)',
    color: 'var(--accent)',
    glow: 'none',
  },
  outline: {
    bg: 'transparent',
    hoverBg: 'rgba(0, 212, 255, 0.06)',
    color: 'var(--accent)',
    glow: 'none',
  },
}

export function GradientBtn({
  children,
  variant = 'primary',
  onClick = null,
  disabled = false,
  loading = false,
  size = 'md',
  icon = null,
  fullWidth = false,
  style = {},
  className = '',
  type = 'button',
}) {
  const v = VARIANT_MAP[variant] || VARIANT_MAP.primary

  const sizeMap = {
    sm: { padding: '6px 14px', fontSize: 'var(--font-size-sm)', minHeight: 32 },
    md: { padding: '10px 20px', fontSize: 'var(--font-size-md)', minHeight: 40 },
    lg: { padding: '14px 28px', fontSize: 'var(--font-size-lg)', minHeight: 48 },
  }
  const sz = sizeMap[size] || sizeMap.md

  const isOutline = variant === 'outline'
  const isGhost = variant === 'ghost'

  return (
    <button
      type={type}
      className={className}
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        background: v.bg,
        color: v.color,
        border: isOutline ? '1px solid var(--border3)' : '1px solid transparent',
        borderRadius: 'var(--radius-md)',
        padding: sz.padding,
        fontSize: sz.fontSize,
        fontWeight: 'var(--font-weight-semibold)',
        fontFamily: 'var(--font)',
        minHeight: sz.minHeight,
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        boxShadow: v.glow,
        opacity: disabled ? 0.5 : 1,
        width: fullWidth ? '100%' : 'auto',
        transition: 'all var(--transition-normal)',
        letterSpacing: '0.3px',
        position: 'relative',
        overflow: 'hidden',
        ...(loading ? { pointerEvents: 'none' } : {}),
        ...style,
      }}
    >
      {loading && (
        <span style={{
          display: 'inline-block',
          width: 16,
          height: 16,
          border: '2px solid rgba(255,255,255,0.3)',
          borderTopColor: '#fff',
          borderRadius: '50%',
          animation: 'spin 0.6s linear infinite',
        }} />
      )}
      {icon && !loading && <span>{icon}</span>}
      {children}
    </button>
  )
}

export default GradientBtn
