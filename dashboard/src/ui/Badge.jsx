/**
 * Severity / status badge component — replaces all inline badge patterns.
 * Animated pulse variant for LIVE badges, glow variants for severity.
 */
const SEVERITY_MAP = {
  CRITICAL: { color: 'var(--danger)', bg: 'rgba(239, 68, 68, 0.15)', glow: 'var(--shadow-glow-danger)' },
  HIGH:     { color: 'var(--warning)', bg: 'rgba(245, 158, 11, 0.15)', glow: 'var(--shadow-glow-warning)' },
  MEDIUM:   { color: 'var(--accent)', bg: 'rgba(79, 124, 255, 0.15)', glow: 'var(--shadow-glow)' },
  LOW:      { color: 'var(--success)', bg: 'rgba(34, 197, 94, 0.15)', glow: 'var(--shadow-glow-success)' },
}

export function Badge({ children, variant = 'default', pulse = false, size = 'sm', style = {}, ...rest }) {
  const sev = SEVERITY_MAP[children] || SEVERITY_MAP[variant] || {}
  const color = sev.color || variant === 'success' ? 'var(--success)' : variant === 'danger' ? 'var(--danger)' : variant === 'warning' ? 'var(--warning)' : 'var(--accent)'
  const bg = sev.bg || variant === 'success' ? 'rgba(34, 197, 94, 0.15)' : variant === 'danger' ? 'rgba(239, 68, 68, 0.15)' : variant === 'warning' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(79, 124, 255, 0.12)'
  const glow = sev.glow

  const padding = size === 'sm' ? '3px 8px' : size === 'md' ? '5px 12px' : '7px 16px'
  const fontSize = size === 'sm' ? 'var(--font-size-xs)' : size === 'md' ? 'var(--font-size-sm)' : 'var(--font-size-md)'

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        background: bg,
        border: `1px solid ${color}33`,
        borderRadius: 'var(--radius-full)',
        padding,
        fontSize,
        fontWeight: 'var(--font-weight-semibold)',
        color,
        letterSpacing: '0.5px',
        textTransform: 'uppercase',
        boxShadow: glow || undefined,
        animation: pulse ? 'glowPulse 2s ease-in-out infinite' : undefined,
        ...style,
      }}
      {...rest}
    >
      {pulse && <span style={{ width: 6, height: 6, borderRadius: '50%', background: color, animation: 'pulse 1.5s ease-in-out infinite' }} />}
      {children}
    </span>
  )
}

export function SourceBadge({ source }) {
  const map = {
    'live':    { color: 'var(--success)', bg: 'rgba(34, 197, 94, 0.12)', label: 'LIVE' },
    'on-chain': { color: 'var(--accent)', bg: 'rgba(79, 124, 255, 0.12)', label: 'ON-CHAIN' },
    'cache':   { color: 'var(--accent2)', bg: 'rgba(124, 95, 255, 0.12)', label: 'CACHED' },
    'fallback': { color: 'var(--warning)', bg: 'rgba(245, 158, 11, 0.12)', label: 'FALLBACK' },
    'seed':    { color: 'var(--text-muted)', bg: 'rgba(123, 139, 168, 0.12)', label: 'SEED' },
  }
  const s = map[source] || map.fallback
  return <Badge variant={s.color === 'var(--success)' ? 'success' : 'default'} size="xs" style={{ background: s.bg, color: s.color }}>{s.label}</Badge>
}
