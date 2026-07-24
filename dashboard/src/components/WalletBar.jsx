/**
 * WalletBar — Premium wallet connection bar using CSPR.click SDK.
 * Shows connected account, balance, and disconnect action.
 */
import { useClickRef, useActiveAccount, truncatePublicKey, connectCasperWallet, disconnectWallet } from '../csprclick.js'
import { GlassCard } from '../ui/GlassCard.jsx'
import { Badge } from '../ui/Badge.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'

export function WalletBar({ style = {} }) {
  const { clickRef, isLoaded, publicKey, provider } = useClickRef()
  const activeAccount = useActiveAccount()

  const isConnected = !!publicKey
  const balance = activeAccount?.balance?.total_balance?.amount
    ? (Number(activeAccount.balance.total_balance.amount) / 1e9).toFixed(2)
    : null

  return (
    <GlassCard hover={false} style={{
      padding: 'var(--space-md)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 'var(--space-md)',
      marginBottom: 'var(--space-sm)',
      ...style,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
        {/* Logo */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-sm)',
        }}>
          <div className="hex-badge" style={{ width: 32, height: 32, fontSize: 14 }}>V</div>
          <span style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-bold)',
            color: 'var(--text)',
            letterSpacing: '-0.5px',
          }}>
            VaultWatch
          </span>
          <Badge size="xs" colorScheme="accent" style={{ fontFamily: 'var(--font-mono)' }}>v5</Badge>
        </div>
      </div>

      {/* Wallet status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
        {isConnected ? (
          <>
            <Badge colorScheme="success" icon="🔑" size="sm">
              {truncatePublicKey(publicKey)}
            </Badge>
            {balance && (
              <span style={{
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-semibold)',
                color: 'var(--accent)',
                fontFamily: 'var(--font-mono)',
              }}>
                {balance} CSPR
              </span>
            )}
            <GradientBtn variant="ghost" size="sm" onClick={() => disconnectWallet(clickRef)}>
              Disconnect
            </GradientBtn>
          </>
        ) : (
          <GradientBtn
            variant="primary"
            size="sm"
            onClick={() => connectCasperWallet(clickRef)}
            disabled={!isLoaded}
            loading={!isLoaded}
            icon="🔗"
          >
            Connect Wallet
          </GradientBtn>
        )}
      </div>
    </GlassCard>
  )
}

export default WalletBar
