/**
 * PageHeader — Premium page header with title, subtitle, breadcrumb, and actions slot.
 */
import { SourceBadge } from './Badge.jsx'

export function PageHeader({
  title,
  subtitle = '',
  icon = null,
  source = null,
  actions = null,
  breadcrumbs = [],
  style = {},
}) {
  return (
    <div className="slide-up" style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--space-sm)',
      marginBottom: 'var(--space-xl)',
      ...style,
    }}>
      {/* Breadcrumbs */}
      {breadcrumbs.length > 0 && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-xs)',
          fontSize: 'var(--font-size-xs)',
          color: 'var(--text-muted)',
        }}>
          {breadcrumbs.map((bc, i) => (
            <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              {i > 0 && <span style={{ color: 'var(--text-dark)' }}>›</span>}
              <span style={{ color: i === breadcrumbs.length - 1 ? 'var(--accent)' : 'var(--text-muted)' }}>
                {bc}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Title row */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 'var(--space-md)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
          {icon && (
            <div style={{
              width: 36,
              height: 36,
              borderRadius: 'var(--radius-md)',
              background: 'var(--gradient-accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 'var(--font-size-lg)',
              boxShadow: 'var(--shadow-glow)',
            }}>
              {icon}
            </div>
          )}
          <div>
            <h2 style={{
              fontSize: 'var(--font-size-2xl)',
              fontWeight: 'var(--font-weight-bold)',
              color: 'var(--text)',
              lineHeight: 1.2,
              margin: 0,
            }}>
              {title}
            </h2>
            {subtitle && (
              <p style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--text-secondary)',
                margin: 0,
                marginTop: 2,
              }}>
                {subtitle}
              </p>
            )}
          </div>
          {source && <SourceBadge source={source} />}
        </div>
        {actions && <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>{actions}</div>}
      </div>
    </div>
  )
}

export default PageHeader
