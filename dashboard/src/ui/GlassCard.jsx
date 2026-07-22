import { useRef, useEffect } from 'react'

/**
 * Glassmorphism card component — the foundation of the premium design system.
 * Replaces all inline `CARD` patterns with a reusable, animated, glass-effect card.
 */
export function GlassCard({ children, style = {}, glow = false, hoverable = true, animated = true, className = '', onClick, ...rest }) {
  const ref = useRef(null)

  useEffect(() => {
    if (animated && ref.current) {
      ref.current.classList.add('fade-in')
    }
  }, [animated])

  const glowShadow = glow
    ? glow === 'success' ? 'var(--shadow-glow-success)'
    : glow === 'danger' ? 'var(--shadow-glow-danger)'
    : glow === 'warning' ? 'var(--shadow-glow-warning)'
    : 'var(--shadow-glow)'
    : ''

  return (
    <div
      ref={ref}
      className={`glass-card ${hoverable ? 'glass-card-hover' : 'glass-card-static'} ${className}`}
      style={{
        padding: 'var(--space-lg)',
        boxShadow: glowShadow ? `${glowShadow}, var(--shadow-inner)` : undefined,
        cursor: onClick ? 'pointer' : undefined,
        ...style,
      }}
      onClick={onClick}
      {...rest}
    >
      {children}
    </div>
  )
}

/**
 * Compact glass card for inline/sub-sections.
 */
export function GlassCardCompact({ children, style = {}, ...rest }) {
  return (
    <GlassCard style={{ padding: 'var(--space-md)', ...style }} {...rest}>
      {children}
    </GlassCard>
  )
}
