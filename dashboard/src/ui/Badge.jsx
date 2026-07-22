/**
 * Badge — Multi-purpose badge with hex, status, and SourceBadge variants.
 * SourceBadge shows data provenance (live, fallback, cache) with color coding.
 */

const STATUS_COLORS = {
  active:   { bg: 'rgba(0, 230, 138, 0.15)', border: 'rgba(0, 230, 138, 0.35)', text: 'var(--success)' },
  inactive: { bg: 'rgba(107, 127, 160, 0.15)', border: 'rgba(107, 127, 160, 0.25)', text: 'var(--text-muted)' },
  error:    { bg: 'rgba(255, 59, 92, 0.15)', border: 'rgba(255, 59, 92, 0.35)', text: 'var(--danger)' },
  pending:  { bg: 'rgba(255, 176, 32, 0.15)', border: 'rgba(255, 176, 32, 0.35)', text: 'var(--warning)' },
  verified: { bg: 'rgba(0, 212, 255, 0.15)', border: 'rgba(0, 212, 255, 0.35)', text: 'var(--accent)' },
}

const SEVERITY_COLORS = {
  CRITICAL: { bg: 'rgba(255, 59, 92, 0.18)', border: 'rgba(255, 59, 92, 0.4)', text: 'var(--danger)', glow: 'var(--shadow-glow-danger)' },
  HIGH:     { bg: 'rgba(255, 59, 92, 0.12)', border: 'rgba(255, 59, 92, 0.3)', text: '#ff6b7a' },
  MEDIUM:   { bg: 'rgba(255, 176, 32, 0.12)', border: 'rgba(255, 176, 32, 0.3)', text: 'var(--warning)' },
  LOW:      { bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.3)', text: 'var(--info)' },
  INFO:     { bg: 'rgba(0, 212, 255, 0.12)', border: 'rgba(0, 212, 255, 0.3)', text: 'var(--accent)' },
}

const SOURCE_COLORS = {
  live:     { bg: 'rgba(0, 230, 138, 0.15)', border: 'rgba(0, 230, 138, 0.35)', text: 'var(--success)', icon: '⚡' },
  fallback: { bg: 'rgba(255, 176, 32, 0.15)', border: 'rgba(255, 176, 32, 0.35)', text: 'var(--warning)', icon: '⟳' },
  cache:    { bg: 'rgba(139, 92, 246, 0.15)', border: 'rgba(139, 92, 246, 0.35)', text: 'var(--accent2)', icon: '💿' },
  seed:     { bg: 'rgba(107, 127, 160, 0.15)', border: 'rgba(107, 127, 160, 0.25)', text: 'var(--text-muted)', icon: '🌱' },
  onchain:  { bg: 'rgba(0, 212, 255, 0.15)', border: 'rgba(0, 212, 255, 0.35)', text: 'var(--accent)', icon: '🔗' },
}

export function Badge({
  children,
  variant = 'default',
  colorScheme = 'accent',
  style = {},
  size = 'sm',
  pulse = false,
  icon = null,
}) {
  const sizeMap = {
    xs: { padding: '2px 6px', fontSize: 'var(--font-size-xs)', gap: 3 },
    sm: { padding: '3px 10px', fontSize: 'var(--font-size-xs)', gap: 4 },
    md: { padding: '4px 14px', fontSize: 'var(--font-size-sm)', gap: 6 },
    lg: { padding: '6px 18px', fontSize: 'var(--font-size-md)', gap: 8 },
  }
  const sz = sizeMap[size] || sizeMap.sm

  const colorMap = {
    accent:  { bg: 'rgba(0, 212, 255, 0.12)', border: 'rgba(0, 212, 255, 0.3)', text: 'var(--accent)' },
    violet:  { bg: 'rgba(139, 92, 246, 0.12)', border: 'rgba(139, 92, 246, 0.3)', text: 'var(--accent2)' },
    success: { bg: 'rgba(0, 230, 138, 0.12)', border: 'rgba(0, 230, 138, 0.3)', text: 'var(--success)' },
    danger:  { bg: 'rgba(255, 59, 92, 0.12)', border: 'rgba(255, 59, 92, 0.3)', text: 'var(--danger)' },
    warning: { bg: 'rgba(255, 176, 32, 0.12)', border: 'rgba(255, 176, 32, 0.3)', text: 'var(--warning)' },
    info:    { bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.3)', text: 'var(--info)' },
    muted:   { bg: 'rgba(107, 127, 160, 0.12)', border: 'rgba(107, 127, 160, 0.2)', text: 'var(--text-muted)' },
  }
  const c = colorMap[colorScheme] || colorMap.accent

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: sz.gap,
      background: c.bg,
      border: `1px solid ${c.border}`,
      borderRadius: 'var(--radius-full)',
      padding: sz.padding,
      fontSize: sz.fontSize,
      fontWeight: 'var(--font-weight-semibold)',
      color: c.text,
      ...(pulse ? { animation: 'pulse 2s ease-in-out infinite' } : {}),
      ...style,
    }}>
      {icon && <span>{icon}</span>}
      {children}
    </span>
  )
}

export function StatusBadge({ status, style = {} }) {
  const c = STATUS_COLORS[status] || STATUS_COLORS.inactive
  return (
    <Badge colorScheme={status === 'active' ? 'success' : status === 'error' ? 'danger' : status === 'pending' ? 'warning' : 'accent'} style={style} pulse={status === 'active'}>
      {status}
    </Badge>
  )
}

export function SeverityBadge({ severity, style = {} }) {
  const c = SEVERITY_COLORS[severity] || SEVERITY_COLORS.INFO
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      background: c.bg,
      border: `1px solid ${c.border}`,
      borderRadius: 'var(--radius-full)',
      padding: '3px 10px',
      fontSize: 'var(--font-size-xs)',
      fontWeight: 'var(--font-weight-bold)',
      color: c.text,
      textTransform: 'uppercase',
      letterSpacing: '0.5px',
      ...(c.glow ? { boxShadow: c.glow } : {}),
      ...style,
    }}>
      {severity}
    </span>
  )
}

export function SourceBadge({ source, style = {} }) {
  const s = String(source || 'fallback').toLowerCase().replace('-', '')
  const c = SOURCE_COLORS[s] || SOURCE_COLORS.fallback
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 3,
      background: c.bg,
      border: `1px solid ${c.border}`,
      borderRadius: 'var(--radius-full)',
      padding: '2px 8px',
      fontSize: 'var(--font-size-xs)',
      fontWeight: 'var(--font-weight-semibold)',
      color: c.text,
      fontFamily: 'var(--font-mono)',
      ...style,
    }}>
      <span>{c.icon}</span>
      {source}
    </span>
  )
}

export function HexBadge({ label, style = {} }) {
  return (
    <span className="hex-badge" style={{ ...style }}>
      {label}
    </span>
  )
}

export default Badge
