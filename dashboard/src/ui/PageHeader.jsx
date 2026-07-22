import { Badge } from './Badge.jsx'

/**
 * Page header — consistent title + badge + subtitle across all panels.
 */
export function PageHeader({ title, badge, subtitle, icon, style = {} }) {
  return (
    <div className="fade-in" style={{
      marginBottom: 'var(--space-lg)',
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--space-md)',
      ...style,
    }}>
      {icon && (
        <div style={{
          fontSize: 'var(--font-size-xl)',
          background: 'var(--gradient-accent)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--space-sm) var(--space-md)',
          display: 'flex',
          alignItems: 'center',
          boxShadow: 'var(--shadow-glow)',
        }}>
          {icon}
        </div>
      )}
      <div style={{ flex: 1 }}>
        <div style={{
          fontSize: 'var(--font-size-xl)',
          fontWeight: 'var(--font-weight-bold)',
          color: 'var(--text)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-sm)',
        }}>
          {title}
          {badge && <Badge size="sm">{badge}</Badge>}
        </div>
        {subtitle && (
          <div style={{
            fontSize: 'var(--font-size-sm)',
            color: 'var(--text-muted)',
            marginTop: 'var(--space-xs)',
          }}>
            {subtitle}
          </div>
        )}
      </div>
    </div>
  )
}

export default PageHeader
