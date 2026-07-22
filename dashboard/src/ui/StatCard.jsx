/**
 * StatCard — Premium stat card with animated counter, icon, and trend indicator.
 */
import { AnimatedCounter } from './AnimatedCounter.jsx'

export function StatCard({
  label,
  value,
  icon = null,
  trend = null,
  trendLabel = '',
  suffix = '',
  prefix = '',
  formatter = null,
  color = 'var(--accent)',
  style = {},
  className = '',
  animated = true,
  source = null,
}) {
  const isPositive = trend && trend > 0
  const isNegative = trend && trend < 0

  const trendColor = isPositive ? 'var(--success)' : isNegative ? 'var(--danger)' : 'var(--text-muted)'
  const trendIcon = isPositive ? '↑' : isNegative ? '↓' : '→'

  const defaultFormatter = (v) => {
    if (typeof v === 'number') {
      if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
      if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`
      if (Number.isInteger(v)) return v.toString()
      return v.toFixed(2)
    }
    return v
  }

  return (
    <div className={`glass-card-static ${className}`} style={{
      padding: 'var(--space-lg)',
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--space-sm)',
      position: 'relative',
      overflow: 'hidden',
      ...style,
    }}>
      {/* Gradient accent line */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: 2,
        background: `linear-gradient(90deg, ${color}, transparent)`,
      }} />

      {/* Label row */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 'var(--space-sm)',
      }}>
        <span style={{
          fontSize: 'var(--font-size-sm)',
          fontWeight: 'var(--font-weight-medium)',
          color: 'var(--text-secondary)',
          letterSpacing: '0.3px',
        }}>
          {icon && <span style={{ marginRight: 6 }}>{icon}</span>}
          {label}
        </span>
        {source && (
          <span style={{
            fontSize: 'var(--font-size-xs)',
            color: source === 'live' ? 'var(--success)' : source === 'fallback' ? 'var(--warning)' : 'var(--accent2)',
            fontFamily: 'var(--font-mono)',
          }}>
            {source === 'live' ? '⚡' : source === 'fallback' ? '⟳' : '💿'}
          </span>
        )}
      </div>

      {/* Value */}
      <div style={{
        fontSize: 'var(--font-size-xl)',
        fontWeight: 'var(--font-weight-bold)',
        color,
        lineHeight: 1.1,
      }}>
        {prefix}
        {animated ? (
          <AnimatedCounter value={value} formatter={formatter || defaultFormatter} />
        ) : (
          (formatter || defaultFormatter)(value)
        )}
        {suffix}
      </div>

      {/* Trend */}
      {trend !== null && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 'var(--font-size-xs)',
          color: trendColor,
          fontWeight: 'var(--font-weight-semibold)',
        }}>
          <span>{trendIcon}</span>
          <span>{Math.abs(trend).toFixed(1)}%</span>
          {trendLabel && <span style={{ color: 'var(--text-muted)' }}>{trendLabel}</span>}
        </div>
      )}
    </div>
  )
}

export default StatCard
