/**
 * Skeleton loading components — shimmer animation placeholders.
 */
export function SkeletonLine({ width = '100%', height = 16, style = {} }) {
  return <div className="skeleton-shimmer" style={{ width, height, ...style }} />
}

export function SkeletonBlock({ width = '100%', height = 80, style = {} }) {
  return <div className="skeleton-shimmer" style={{ width, height, borderRadius: 'var(--radius-md)', ...style }} />
}

export function SkeletonCircle({ size = 40, style = {} }) {
  return <div className="skeleton-shimmer" style={{ width: size, height: size, borderRadius: '50%', ...style }} />
}

export function SkeletonTable({ rows = 5, cols = 4, style = {} }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', ...style }}>
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} style={{ display: 'flex', gap: 'var(--space-md)' }}>
          {Array.from({ length: cols }, (_, c) => (
            <SkeletonLine key={c} width={c === 0 ? '30%' : `${70 / (cols - 1)}%`} height={14} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonCard({ style = {} }) {
  return (
    <div className="glass-card-static" style={{ padding: 'var(--space-lg)', ...style }}>
      <SkeletonLine width="40%" height={20} style={{ marginBottom: 'var(--space-md)' }} />
      <SkeletonLine width="100%" height={14} style={{ marginBottom: 'var(--space-sm)' }} />
      <SkeletonLine width="80%" height={14} />
    </div>
  )
}
