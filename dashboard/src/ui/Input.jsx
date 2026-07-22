/**
 * Styled form input component — replaces all inline `INPUT` patterns.
 * Supports glass style, focus glow, error state, and multiple types.
 */
export function Input({ value, onChange, placeholder, type = 'text', label, error, glass = true, style = {}, ...rest }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)', ...style }}>
      {label && (
        <label style={{
          fontSize: 'var(--font-size-xs)',
          fontWeight: 'var(--font-weight-medium)',
          color: 'var(--text-muted)',
          letterSpacing: '0.5px',
          textTransform: 'uppercase',
        }}>
          {label}
        </label>
      )}
      {type === 'textarea' ? (
        <textarea
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          style={{
            background: glass ? 'var(--glass-bg)' : 'var(--surface)',
            border: `1px solid ${error ? 'var(--danger)' : 'var(--glass-border)'}`,
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-md)',
            fontSize: 'var(--font-size-md)',
            fontFamily: 'var(--font)',
            color: 'var(--text)',
            resize: 'vertical',
            minHeight: 80,
            outline: 'none',
            transition: 'border-color var(--transition-fast)',
            backdropFilter: glass ? 'blur(var(--glass-blur))' : 'none',
          }}
          onFocus={e => { e.target.style.borderColor = error ? 'var(--danger)' : 'var(--accent)' }}
          onBlur={e => { e.target.style.borderColor = error ? 'var(--danger)' : 'var(--glass-border)' }}
          {...rest}
        />
      ) : type === 'select' ? (
        <select
          value={value}
          onChange={onChange}
          style={{
            background: glass ? 'var(--glass-bg)' : 'var(--surface)',
            border: `1px solid ${error ? 'var(--danger)' : 'var(--glass-border)'}`,
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-md)',
            fontSize: 'var(--font-size-md)',
            fontFamily: 'var(--font)',
            color: 'var(--text)',
            outline: 'none',
            transition: 'border-color var(--transition-fast)',
          }}
          {...rest}
        />
      ) : (
        <input
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          style={{
            background: glass ? 'var(--glass-bg)' : 'var(--surface)',
            border: `1px solid ${error ? 'var(--danger)' : 'var(--glass-border)'}`,
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-md)',
            fontSize: 'var(--font-size-md)',
            fontFamily: 'var(--font)',
            color: 'var(--text)',
            outline: 'none',
            transition: 'border-color var(--transition-fast)',
            backdropFilter: glass ? 'blur(var(--glass-blur))' : 'none',
          }}
          onFocus={e => { e.target.style.borderColor = error ? 'var(--danger)' : 'var(--accent)' }}
          onBlur={e => { e.target.style.borderColor = error ? 'var(--danger)' : 'var(--glass-border)' }}
          {...rest}
        />
      )}
      {error && (
        <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--danger)' }}>{error}</span>
      )}
    </div>
  )
}
