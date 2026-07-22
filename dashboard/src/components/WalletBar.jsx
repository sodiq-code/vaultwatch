// WalletBar — premium glass top-of-dashboard CSPR.click wallet connection bar.
//
// Renders the CSPR.click status indicator plus our own compact status strip showing:
//   * the connected account's truncated public key + wallet name, with a
//     "Disconnect" button, OR
//   * a "Connect Wallet" button that calls clickRef.connect('casper-wallet'),
//   * a "Powered by CSPR.click" badge linking to https://cspr.build/cspr-click.
//
// Follows SKILL.md: no SDK method is called before `csprclick:loaded` (the
// provider only exposes `clickRef` after load, and all click handlers guard
// on `clickRef`), and the Disconnect button uses `disconnect()` (NOT
// `signOut()`) per the "signOut() ≠ disconnect()" constraint.

import { useClickRef, truncatePublicKey, connectCasperWallet, disconnectWallet } from '../csprclick.js'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { Badge } from '../ui/Badge.jsx'
import { useResponsive } from '../hooks/useResponsive.js'

const SUPPORTED_WALLET_LABEL = 'Casper Wallet'

// Wallet SVG icon (inline, no external dependency)
const WalletIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="2" y="6" width="20" height="14" rx="2" />
    <path d="M16 14h2v-2h-2" />
    <path d="M6 6V4a2 2 0 012-2h8a2 2 0 012 2v2" />
  </svg>
)

// Disconnect SVG icon
const DisconnectIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M18 6L6 18" />
    <path d="M6 6l12 12" />
  </svg>
)

export default function WalletBar() {
  const { clickRef, isLoaded, activeAccount, publicKey, provider } = useClickRef()
  const { isMobile } = useResponsive()

  const connected = !!(activeAccount && publicKey)
  // Pretty wallet label — fall back to the provider key or the canonical
  // "Casper Wallet" name when the SDK doesn't expose a friendly name.
  const walletLabel =
    (activeAccount && (activeAccount.name || activeAccount.provider)) ||
    (provider === 'casper-wallet' ? SUPPORTED_WALLET_LABEL : provider) ||
    SUPPORTED_WALLET_LABEL

  const onConnect = () => {
    if (!clickRef) {
      // eslint-disable-next-line no-console
      console.warn('[WalletBar] CSPR.click SDK not loaded yet — ignoring connect click')
      return
    }
    // SKILL.md / methods.md: connect(provider, options?) requests a direct
    // connection via the named wallet provider. We pass WALLET_KEYS.CASPER_WALLET
    // ('casper-wallet') — the canonical provider string per the Types reference.
    connectCasperWallet(clickRef)
  }

  const onDisconnect = () => {
    if (!clickRef) {
      // eslint-disable-next-line no-console
      console.warn('[WalletBar] CSPR.click SDK not loaded yet — ignoring disconnect click')
      return
    }
    // SKILL.md: use disconnect() (NOT signOut()) for the Disconnect button —
    // disconnect() revokes the wallet's connection permission.
    disconnectWallet(clickRef)
  }

  return (
    <div
      role="region"
      aria-label="Wallet connection"
      style={{
        // ── Glass bar background ──
        background: 'var(--glass-bg)',
        backdropFilter: 'blur(var(--glass-blur)) saturate(var(--glass-saturate))',
        WebkitBackdropFilter: 'blur(var(--glass-blur)) saturate(var(--glass-saturate))',
        // ── Glass borders (gradient bottom border applied via overlay div) ──
        border: '1px solid var(--glass-border)',
        boxShadow: 'var(--shadow-md), var(--shadow-inner)',
        padding: isMobile ? '6px 10px' : '8px var(--space-lg)',
        display: 'flex',
        alignItems: 'center',
        gap: isMobile ? 8 : 12,
        flexShrink: 0,
        minHeight: isMobile ? 40 : 44,
        fontSize: 'var(--font-size-sm)',
        zIndex: 5,
        position: 'relative',
      }}
    >
      {/* ── Gradient accent bottom border overlay ──
          Using a positioned overlay div because CSS border-image
          is incompatible with border-radius. This div renders the
          gradient at the bar's bottom edge while keeping rounded corners. */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          bottom: -1,
          left: -1,
          right: -1,
          height: 2,
          background: 'var(--gradient-accent)',
          borderRadius: '0 0 var(--radius-md) var(--radius-md)',
          zIndex: 1,
        }}
      />

      {/* ── CSPR.click status indicator ── */}
      <span
        aria-hidden="true"
        title="CSPR.click top bar mounts into #csprclick-ui in index.html"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          color: 'var(--text-muted)',
          fontSize: 'var(--font-size-xs)',
          flexShrink: 0,
          fontFamily: 'var(--font)',
        }}
      >
        {/* Status dot — glowPulse animation when connected */}
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: connected
              ? 'var(--success)'
              : isLoaded
                ? 'var(--success)'
                : 'var(--text-muted)',
            boxShadow: connected
              ? '0 0 8px rgba(34, 197, 94, 0.4), 0 0 16px rgba(34, 197, 94, 0.2)'
              : isLoaded
                ? '0 0 6px rgba(34, 197, 94, 0.3)'
                : 'none',
            animation: connected ? 'glowPulseGreen 2s ease-in-out infinite' : 'none',
            flexShrink: 0,
            transition: 'all var(--transition-normal)',
          }}
        />
        {isMobile
          ? (isLoaded ? 'Ready' : 'Loading…')
          : (isLoaded ? 'CSPR.click ready' : 'Loading CSPR.click…')
        }
      </span>

      <div style={{ flex: 1 }} />

      {/* ── Connected account chip OR connect button ── */}
      {connected ? (
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: isMobile ? 6 : 10,
            // ── Glass chip with accent glow ──
            background: 'var(--glass-bg)',
            backdropFilter: 'blur(var(--glass-blur)) saturate(var(--glass-saturate))',
            WebkitBackdropFilter: 'blur(var(--glass-blur)) saturate(var(--glass-saturate))',
            border: '1px solid var(--glass-border)',
            borderRadius: 'var(--radius-md)',
            padding: isMobile ? '4px 10px 4px 12px' : '5px 14px 5px 16px',
            fontSize: 'var(--font-size-xs)',
            boxShadow: 'var(--shadow-glow), var(--shadow-inner)',
            animation: 'glowPulse 3s ease-in-out infinite',
            transition: 'all var(--transition-normal)',
          }}
        >
          {/* Wallet label */}
          <span
            title={`Connected via ${walletLabel}`}
            style={{
              color: 'var(--text-muted)',
              fontSize: 'var(--font-size-xs)',
              textTransform: 'uppercase',
              letterSpacing: 0.5,
              fontFamily: 'var(--font)',
              fontWeight: 'var(--font-weight-medium)',
              display: isMobile ? 'none' : 'inline',
            }}
          >
            {walletLabel}
          </span>

          {/* Truncated public key */}
          <code
            title={publicKey}
            style={{
              color: 'var(--text)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--font-size-xs)',
              fontWeight: 'var(--font-weight-medium)',
              letterSpacing: '0.3px',
            }}
          >
            {truncatePublicKey(publicKey)}
          </code>

          {/* Disconnect button — GradientBtn ghost with danger hover glow */}
          <GradientBtn
            variant="ghost"
            size="sm"
            onClick={onDisconnect}
            aria-label="Disconnect wallet"
            style={{
              fontSize: 'var(--font-size-xs)',
              padding: '3px 10px',
              borderRadius: 'var(--radius-sm)',
              boxShadow: 'none',
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={(e) => {
              const btn = e.currentTarget
              btn.style.color = 'var(--danger)'
              btn.style.borderColor = 'var(--danger)'
              btn.style.background = 'rgba(239, 68, 68, 0.12)'
              btn.style.boxShadow = 'var(--shadow-glow-danger)'
            }}
            onMouseLeave={(e) => {
              const btn = e.currentTarget
              btn.style.color = 'var(--text-muted)'
              btn.style.borderColor = 'var(--glass-border)'
              btn.style.background = 'var(--surface3)'
              btn.style.boxShadow = 'none'
            }}
          >
            <DisconnectIcon />
            {isMobile ? '' : 'Disconnect'}
          </GradientBtn>
        </div>
      ) : (
        <GradientBtn
          variant="accent"
          size="sm"
          onClick={onConnect}
          disabled={!isLoaded}
          aria-label="Connect Casper wallet"
          style={{
            boxShadow: isLoaded ? 'var(--shadow-glow)' : 'none',
            transition: 'all var(--transition-normal)',
          }}
          onMouseEnter={(e) => {
            if (!isLoaded) return
            const btn = e.currentTarget
            btn.style.boxShadow = 'var(--shadow-glow), 0 0 30px rgba(79, 124, 255, 0.4)'
          }}
          onMouseLeave={(e) => {
            const btn = e.currentTarget
            btn.style.boxShadow = isLoaded ? 'var(--shadow-glow)' : 'none'
          }}
        >
          <WalletIcon />
          {isMobile ? 'Connect' : 'Connect Wallet'}
        </GradientBtn>
      )}

      {/* ── "Powered by CSPR.click" badge ── */}
      <Badge
        variant="default"
        size="sm"
        pulse={false}
        style={{
          // ── Glass badge with subtle accent glow ──
          background: 'var(--glass-bg)',
          backdropFilter: 'blur(var(--glass-blur)) saturate(var(--glass-saturate))',
          WebkitBackdropFilter: 'blur(var(--glass-blur)) saturate(var(--glass-saturate))',
          border: '1px solid var(--glass-border)',
          boxShadow: '0 0 12px rgba(79, 124, 255, 0.15), var(--shadow-inner)',
          color: 'var(--text-muted)',
          textTransform: 'none',
          letterSpacing: '0',
          fontWeight: 'var(--font-weight-medium)',
          cursor: 'pointer',
          transition: 'all var(--transition-normal)',
          flexShrink: 0,
        }}
      >
        <a
          href="https://cspr.build/cspr-click"
          target="_blank"
          rel="noopener noreferrer"
          title="Powered by CSPR.click — open in a new tab"
          style={{
            color: 'inherit',
            textDecoration: 'none',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
          }}
          onMouseEnter={(e) => {
            const badge = e.currentTarget.closest('span')
            if (badge) {
              badge.style.color = 'var(--accent)'
              badge.style.borderColor = 'var(--accent)'
              badge.style.boxShadow = 'var(--shadow-glow)'
            }
          }}
          onMouseLeave={(e) => {
            const badge = e.currentTarget.closest('span')
            if (badge) {
              badge.style.color = 'var(--text-muted)'
              badge.style.borderColor = 'var(--glass-border)'
              badge.style.boxShadow = '0 0 12px rgba(79, 124, 255, 0.15), var(--shadow-inner)'
            }
          }}
        >
          {isMobile ? 'CSPR.click' : (
            <>
              Powered by
              <strong style={{ color: 'var(--text)', fontWeight: 'var(--font-weight-bold)' }}>CSPR.click</strong>
            </>
          )}
        </a>
      </Badge>
    </div>
  )
}
