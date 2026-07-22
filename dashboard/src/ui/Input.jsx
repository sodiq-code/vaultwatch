/**
 * Input — Premium styled input with label, icon, and clear button.
 */
import { useState } from 'react'

export function Input({
  value = '',
  onChange = null,
  placeholder = '',
  label = '',
  icon = null,
  type = 'text',
  disabled = false,
  maxLength = null,
  style = {},
  className = '',
  name = '',
  autoFocus = false,
  onKeyDown = null,
  clearable = false,
  mono = false,
}) {
  const [focused, setFocused] = useState(false)

  return (
    <div className={className} style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      ...style,
    }}>
      {label && (
        <label style={{
          fontSize: 'var(--font-size-sm)',
          fontWeight: 'var(--font-weight-medium)',
          color: focused ? 'var(--accent)' : 'var(--text-secondary)',
          transition: 'color var(--transition-fast)',
        }}>
          {label}
        </label>
      )}
      <div style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
      }}>
        {icon && (
          <span style={{
            position: 'absolute',
            left: 12,
            color: focused ? 'var(--accent)' : 'var(--text-muted)',
            fontSize: 'var(--font-size-md)',
            transition: 'color var(--transition-fast)',
          }}>
            {icon}
          </span>
        )}
        <input
          name={name}
          type={type}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          maxLength={maxLength}
          autoFocus={autoFocus}
          onKeyDown={onKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
            width: '100%',
            background: focused ? 'rgba(0, 212, 255, 0.04)' : 'var(--glass-bg)',
            border: `1px solid ${focused ? 'var(--border3)' : 'var(--glass-border)'}`,
            borderRadius: 'var(--radius-md)',
            padding: `10px ${clearable ? 36 : 14}px ${icon ? 36 : 14}px`,
            fontSize: 'var(--font-size-md)',
            fontWeight: 'var(--font-weight-normal)',
            fontFamily: mono ? 'var(--font-mono)' : 'var(--font)',
            color: 'var(--text)',
            outline: 'none',
            transition: 'all var(--transition-fast)',
            ...(disabled ? { opacity: 0.5, cursor: 'not-allowed' } : {}),
          }}
        />
        {clearable && value && (
          <button
            onClick={() => onChange?.('')}
            style={{
              position: 'absolute',
              right: 8,
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: 'var(--font-size-sm)',
              padding: 4,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            ✕
          </button>
        )}
      </div>
    </div>
  )
}

export default Input
