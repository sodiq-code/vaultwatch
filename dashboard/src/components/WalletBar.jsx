// WalletBar — top-of-dashboard CSPR.click wallet connection bar.
//
// Renders the CSPR.click UI mount point (the SDK injects the official top bar
// into <div id="csprclick-ui"> already present in index.html), plus our own
// compact status strip showing:
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

const SUPPORTED_WALLET_LABEL = 'Casper Wallet'

export default function WalletBar() {
  const { clickRef, isLoaded, activeAccount, publicKey, provider } = useClickRef()

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
        background: 'linear-gradient(90deg, #0d0f1a 0%, #161929 100%)',
        borderBottom: '1px solid var(--border)',
        padding: '6px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexShrink: 0,
        minHeight: 36,
        fontSize: 12,
        zIndex: 5,
      }}
    >
      {/* CSPR.click UI mount point. The SDK injects the official top bar / wallet
          menu here. This div is ALSO present in index.html as the first child
          of <body> (per the SKILL.md "as close as possible to the opening body
          tag" constraint); rendering it again here would create a duplicate id,
          so we only render a fallback notice when the SDK has not yet mounted
          its UI. */}
      <span
        aria-hidden="true"
        title="CSPR.click top bar mounts into #csprclick-ui in index.html"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          color: 'var(--text-muted)',
          fontSize: 10,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: isLoaded ? 'var(--success)' : 'var(--text-muted)',
            boxShadow: isLoaded ? '0 0 6px #22c55e80' : 'none',
            flexShrink: 0,
          }}
        />
        {isLoaded ? 'CSPR.click ready' : 'Loading CSPR.click…'}
      </span>

      <div style={{ flex: 1 }} />

      {/* Connected account chip OR connect button */}
      {connected ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'var(--surface2)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '3px 8px 3px 10px',
            fontSize: 11,
          }}
        >
          <span
            title={`Connected via ${walletLabel}`}
            style={{
              color: 'var(--text-muted)',
              fontSize: 10,
              textTransform: 'uppercase',
              letterSpacing: 0.5,
            }}
          >
            {walletLabel}
          </span>
          <code
            title={publicKey}
            style={{
              color: 'var(--text)',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
              fontSize: 11,
            }}
          >
            {truncatePublicKey(publicKey)}
          </code>
          <button
            type="button"
            onClick={onDisconnect}
            aria-label="Disconnect wallet"
            style={{
              background: 'transparent',
              border: '1px solid var(--border)',
              color: 'var(--text-muted)',
              borderRadius: 6,
              padding: '2px 8px',
              fontSize: 10,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--danger)'
              e.currentTarget.style.borderColor = 'var(--danger)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--text-muted)'
              e.currentTarget.style.borderColor = 'var(--border)'
            }}
          >
            Disconnect
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={onConnect}
          disabled={!isLoaded}
          aria-label="Connect Casper wallet"
          style={{
            background: isLoaded ? 'var(--accent)' : 'var(--surface2)',
            border: '1px solid var(--accent)',
            color: isLoaded ? '#fff' : 'var(--text-muted)',
            borderRadius: 8,
            padding: '4px 14px',
            fontSize: 12,
            fontWeight: 600,
            cursor: isLoaded ? 'pointer' : 'not-allowed',
            transition: 'all 0.15s',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
          }}
          onMouseEnter={(e) => {
            if (!isLoaded) return
            e.currentTarget.style.background = 'var(--accent2)'
            e.currentTarget.style.borderColor = 'var(--accent2)'
          }}
          onMouseLeave={(e) => {
            if (!isLoaded) return
            e.currentTarget.style.background = 'var(--accent)'
            e.currentTarget.style.borderColor = 'var(--accent)'
          }}
        >
          <span aria-hidden="true">🔗</span>
          Connect Wallet
        </button>
      )}

      {/* "Powered by CSPR.click" badge */}
      <a
        href="https://cspr.build/cspr-click"
        target="_blank"
        rel="noopener noreferrer"
        title="Powered by CSPR.click — open in a new tab"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          color: 'var(--text-muted)',
          fontSize: 10,
          textDecoration: 'none',
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: '2px 7px',
          background: 'var(--surface)',
          flexShrink: 0,
          transition: 'all 0.15s',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = 'var(--accent)'
          e.currentTarget.style.borderColor = 'var(--accent)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = 'var(--text-muted)'
          e.currentTarget.style.borderColor = 'var(--border)'
        }}
      >
        Powered by
        <strong style={{ color: 'var(--text)', fontWeight: 700 }}>CSPR.click</strong>
      </a>
    </div>
  )
}
