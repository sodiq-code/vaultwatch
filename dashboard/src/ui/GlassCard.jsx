/**
 * GlassCard — Premium glassmorphism card with gradient overlay and hover effects.
 * Uses the design system CSS variables extensively.
 */
import { useState } from 'react'

export function GlassCard({
  children,
  className = '',
  style = {},
  hover = true,
  glow = false,
  glowColor = 'cyan',
  padding = 'var(--space-lg)',
  onClick = null,
  animated = false,
  tag = null,
  ...rest
}) {
  const [isHovered, setIsHovered] = useState(false)

  const glowMap = {
    cyan: 'var(--shadow-glow)',
    violet: 'var(--shadow-glow2)',
    success: 'var(--shadow-glow-success)',
    danger: 'var(--shadow-glow-danger)',
    warning: 'var(--shadow-glow-warning)',
  }

  const baseClass = hover ? 'glass-card' : 'glass-card-static'
  const animClass = animated ? 'slide-up' : ''
  const classes = [baseClass, animClass, className].filter(Boolean).join(' ')

  const computedStyle = {
    padding,
    ...(glow ? { boxShadow: `${glowMap[glowColor] || glowMap.cyan}, var(--shadow-card)` } : {}),
    ...(onClick ? { cursor: 'pointer' } : {}),
    ...(isHovered && hover ? {
      transform: 'translateY(-2px)',
      boxShadow: `${glowMap[glowColor] || glowMap.cyan}, var(--shadow-lg), var(--shadow-inner)`,
    } : {}),
    ...style,
  }

  return (
    <div
      className={classes}
      style={computedStyle}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      {...rest}
    >
      {tag && (
        <div style={{
          position: 'absolute',
          top: -8,
          right: 12,
          background: 'var(--gradient-accent)',
          color: '#fff',
          fontSize: 'var(--font-size-xs)',
          fontWeight: 'var(--font-weight-bold)',
          padding: '2px 10px',
          borderRadius: 'var(--radius-full)',
          boxShadow: 'var(--shadow-glow)',
          letterSpacing: '0.5px',
        }}>
          {tag}
        </div>
      )}
      {children}
    </div>
  )
}

export default GlassCard
