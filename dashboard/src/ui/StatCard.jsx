import { useEffect, useRef, useState } from 'react'

/**
 * Animated stat card — large number + label with smooth counter animation.
 */
export function StatCard({ value, label, sub, color, icon, prefix = '', suffix = '', style = {}, loading = false, className = '' }) {
  const displayValue = loading ? null : value
  const colorVar = color === 'success' ? 'var(--success)'
    : color === 'danger' ? 'var(--danger)'
    : color === 'warning' ? 'var(--warning)'
    : color === 'accent' ? 'var(--accent)'
    : 'var(--text)'

  return (
    <div className={`glass-card-static slide-up ${className}`} style={{
      padding: 'var(--space-md)',
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--space-xs)',
      ...style,
    }}>
      {loading ? (
        <div className="skeleton-shimmer" style={{ width: 60, height: 28, marginBottom: 4 }} />
      ) : (
        <div style={{
          fontSize: 'var(--font-size-2xl)',
          fontWeight: 'var(--font-weight-bold)',
          color: colorVar,
          lineHeight: 1.1,
        }}>
          {prefix}{displayValue !== null ? (typeof displayValue === 'number' ? formatNumber(displayValue) : displayValue) : '—'}{suffix}
        </div>
      )}
      <div style={{
        fontSize: 'var(--font-size-xs)',
        fontWeight: 'var(--font-weight-medium)',
        color: 'var(--text-muted)',
        letterSpacing: '0.5px',
        textTransform: 'uppercase',
      }}>
        {icon && <span style={{ marginRight: 4 }}>{icon}</span>}
        {label}
      </div>
      {sub && !loading && (
        <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 2 }}>
          {sub}
        </div>
      )}
    </div>
  )
}

function formatNumber(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  if (typeof n === 'number' && !Number.isInteger(n)) return n.toFixed(2)
  return String(n)
}

export default StatCard
