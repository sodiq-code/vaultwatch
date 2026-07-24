import { useToast } from '../hooks/useToast.js'

/**
 * Toast notification container — renders transient success/error/warning/info messages.
 * Fixed bottom-right positioning with slide-in/out animations.
 */
const TOAST_STYLES = {
  success: { bg: 'rgba(34, 197, 94, 0.15)', border: 'rgba(34, 197, 94, 0.3)', color: 'var(--success)', glow: 'var(--shadow-glow-success)', icon: '✓' },
  error:   { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.3)', color: 'var(--danger)', glow: 'var(--shadow-glow-danger)', icon: '✕' },
  warning: { bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.3)', color: 'var(--warning)', glow: 'var(--shadow-glow-warning)', icon: '⚠' },
  info:    { bg: 'rgba(79, 124, 255, 0.15)', border: 'rgba(79, 124, 255, 0.3)', color: 'var(--accent)', glow: 'var(--shadow-glow)', icon: 'ℹ' },
}

export function ToastContainer({ toasts, removeToast }) {
  if (!toasts || toasts.length === 0) return null

  return (
    <div style={{
      position: 'fixed',
      bottom: 'var(--space-lg)',
      right: 'var(--space-lg)',
      zIndex: 'var(--z-toast)',
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--space-sm)',
      maxWidth: 380,
    }}>
      {toasts.map(toast => {
        const s = TOAST_STYLES[toast.type] || TOAST_STYLES.info
        return (
          <div
            key={toast.id}
            className="slide-up"
            style={{
              background: s.bg,
              backdropFilter: 'blur(8px)',
              border: `1px solid ${s.border}`,
              borderRadius: 'var(--radius-md)',
              padding: 'var(--space-md) var(--space-lg)',
              boxShadow: s.glow,
              color: s.color,
              fontSize: 'var(--font-size-sm)',
              fontWeight: 'var(--font-weight-medium)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              cursor: 'pointer',
              animation: 'toastIn 0.25s ease-out',
            }}
            onClick={() => removeToast(toast.id)}
          >
            <span style={{ fontSize: 'var(--font-size-lg)' }}>{s.icon}</span>
            <span>{toast.message}</span>
          </div>
        )
      })}
    </div>
  )
}
