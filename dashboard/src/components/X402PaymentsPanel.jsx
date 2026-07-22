/**
 * X402PaymentsPanel — Payment flow visualization, subscription status,
 * plan pricing, recent payments.
 */
import { useState, useEffect } from 'react'
import { GlassCard } from '../ui/GlassCard.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { Badge, SourceBadge } from '../ui/Badge.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { SkeletonBlock } from '../ui/Skeleton.jsx'
import { CONTRACT_HASHES } from '../liveApi.js'

export function X402PaymentsPanel({ api, addToast }) {
  const [x402Status, setX402Status] = useState(null)
  const [loading, setLoading] = useState(true)
  const [source, setSource] = useState(null)

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 20000)
    return () => clearInterval(interval)
  }, [])

  const loadStatus = async () => {
    try {
      const data = await api.getX402Status()
      if (data) {
        setX402Status(data)
        setSource(data._source || 'fallback')
      }
    } catch (e) {
      // Keep stale
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 'var(--space-lg)' }}>
        <SkeletonBlock height={40} style={{ marginBottom: 'var(--space-lg)' }} />
        <SkeletonBlock height={300} />
      </div>
    )
  }

  if (!x402Status) {
    return (
      <GlassCard hover={false} style={{ padding: 'var(--space-xl)', textAlign: 'center' }}>
        <div style={{ color: 'var(--danger)', fontSize: 'var(--font-size-lg)' }}>x402 Status Unavailable</div>
      </GlassCard>
    )
  }

  const contracts = x402Status.contracts || {}
  const plans = x402Status.planPrices || {}
  const payments = x402Status.recentPayments || []
  const sdkInfo = x402Status.sdk || {}

  return (
    <div className="fade-in" style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="x402 Payments"
        subtitle="Casper x402 exact-scheme payment flow & subscription status"
        icon="💰"
        source={source}
      />

      {/* Stats */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 'var(--space-md)',
        marginBottom: 'var(--space-lg)',
      }}>
        <StatCard label="x402 Version" value={x402Status.x402Version || '—'} icon="📦" color="var(--accent)" animated={false} />
        <StatCard label="Scheme" value={x402Status.scheme || 'exact'} icon="⚙️" color="var(--accent2)" animated={false} />
        <StatCard label="Network" value={x402Status.network || 'casper-test'} icon="🔗" color="var(--success)" animated={false} />
        <StatCard label="Recent Payments" value={payments.length} icon="💳" color="var(--warning)" />
      </div>

      {/* Two column layout */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--space-lg)',
        marginBottom: 'var(--space-lg)',
      }}>
        {/* Payment flow visualization */}
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
            marginBottom: 'var(--space-md)',
          }}>
            Payment Flow
          </div>

          {/* Flow diagram */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-sm)',
            padding: 'var(--space-md)',
            background: 'rgba(0, 212, 255, 0.04)',
            borderRadius: 'var(--radius-md)',
          }}>
            {[
              { label: 'User Request', icon: '👤', color: 'var(--accent)' },
              { label: 'x402 Interceptor', icon: '🔒', color: 'var(--warning)' },
              { label: 'Vault Unlock', icon: '🔓', color: 'var(--success)' },
              { label: 'Open Vault Entry', icon: '📊', color: 'var(--accent2)' },
              { label: 'Data Delivered', icon: '✅', color: 'var(--success)' },
            ].map((step, i) => (
              <div key={i} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                padding: '8px 12px',
                background: 'rgba(14, 18, 30, 0.5)',
                borderRadius: 'var(--radius-sm)',
              }}>
                <span style={{ fontSize: 16 }}>{step.icon}</span>
                <span style={{
                  fontSize: 'var(--font-size-sm)',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: step.color,
                  flex: 1,
                }}>
                  {step.label}
                </span>
                <span style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-muted)',
                }}>
                  {i < 4 ? '→' : '✓'}
                </span>
              </div>
            ))}
          </div>

          {/* Helper / signer availability */}
          <div style={{
            marginTop: 'var(--space-md)',
            display: 'flex',
            gap: 'var(--space-sm)',
          }}>
            <Badge colorScheme={x402Status.helperAvailable ? 'success' : 'danger'} size="sm" icon={x402Status.helperAvailable ? '✓' : '✕'}>
              Helper Available
            </Badge>
            <Badge colorScheme={x402Status.signerAvailable ? 'success' : 'danger'} size="sm" icon={x402Status.signerAvailable ? '✓' : '✕'}>
              Signer Available
            </Badge>
          </div>
        </GlassCard>

        {/* Plan pricing */}
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
            marginBottom: 'var(--space-md)',
          }}>
            Subscription Plans
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            {Object.entries(plans).map(([planName, planData]) => (
              <div key={planName} style={{
                padding: 'var(--space-lg)',
                background: planName === 'premium' ? 'rgba(139, 92, 246, 0.08)' : 'rgba(0, 212, 255, 0.06)',
                border: `1px solid ${planName === 'premium' ? 'rgba(139, 92, 246, 0.2)' : 'rgba(0, 212, 255, 0.15)'}`,
                borderRadius: 'var(--radius-lg)',
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 'var(--space-sm)',
                }}>
                  <div style={{
                    fontSize: 'var(--font-size-lg)',
                    fontWeight: 'var(--font-weight-bold)',
                    color: planName === 'premium' ? 'var(--accent2)' : 'var(--accent)',
                    textTransform: 'uppercase',
                  }}>
                    {planName}
                  </div>
                  <Badge size="sm" colorScheme={planName === 'premium' ? 'violet' : 'accent'}>
                    {planData.queries} queries
                  </Badge>
                </div>
                <div style={{
                  fontSize: 'var(--font-size-2xl)',
                  fontWeight: 'var(--font-weight-bold)',
                  color: 'var(--text)',
                  lineHeight: 1,
                }}>
                  {planData.amount_cspr} CSPR
                </div>
                <div style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                  marginTop: 4,
                }}>
                  {planData.amount_motes?.toLocaleString()} motes
                </div>
              </div>
            ))}
          </div>

          {/* SDK info */}
          <div style={{
            marginTop: 'var(--space-md)',
            padding: 'var(--space-sm)',
            background: 'rgba(14, 18, 30, 0.4)',
            borderRadius: 'var(--radius-sm)',
            fontSize: 'var(--font-size-xs)',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
          }}>
            <div style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--text-secondary)', marginBottom: 4 }}>SDK Dependencies</div>
            {Object.entries(sdkInfo).map(([pkg, ver]) => (
              <div key={pkg}>{pkg}: {ver}</div>
            ))}
          </div>
        </GlassCard>
      </div>

      {/* Contract info */}
      <GlassCard hover={false} style={{ padding: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        <div style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-semibold)',
          color: 'var(--text)',
          marginBottom: 'var(--space-md)',
        }}>
          Smart Contracts
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {Object.entries(contracts).map(([name, info]) => (
            <div key={name} className="glass-row-hover" style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-md)',
              padding: 'var(--space-md)',
              background: 'rgba(14, 18, 30, 0.4)',
              borderRadius: 'var(--radius-md)',
            }}>
              <Badge size="sm" colorScheme="accent">{name}</Badge>
              <div style={{
                flex: 1,
                fontSize: 'var(--font-size-sm)',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                wordBreak: 'break-all',
              }}>
                {info.contractHash?.slice(0, 16)}…{info.contractHash?.slice(-8)}
              </div>
              <Badge size="xs" colorScheme="muted">{info.entryPoint}</Badge>
              <SourceBadge source={source} />
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Recent payments */}
      <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
        <div style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-semibold)',
          color: 'var(--text)',
          marginBottom: 'var(--space-md)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-sm)',
        }}>
          Recent Payments
          <Badge size="sm" colorScheme="accent">{payments.length}</Badge>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {payments.map((payment, i) => (
            <div key={payment.id || i} className="glass-row-hover" style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              padding: 'var(--space-md)',
              background: 'rgba(14, 18, 30, 0.4)',
              borderRadius: 'var(--radius-md)',
            }}>
              <Badge size="sm" colorScheme={payment.plan === 'premium' ? 'violet' : 'accent'}>{payment.plan}</Badge>
              <div style={{
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-semibold)',
                color: 'var(--text)',
              }}>
                {payment.amount_cspr} CSPR
              </div>
              <div style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
              }}>
                {payment.subscriber?.slice(0, 10)}…
              </div>
              <div style={{
                flex: 1,
                fontSize: 'var(--font-size-xs)',
                color: 'var(--text-dark)',
                fontFamily: 'var(--font-mono)',
              }}>
                {payment.deploy_hash?.slice(0, 12)}…
              </div>
              <Badge size="xs" colorScheme={payment.status === 'verified' ? 'success' : payment.status === 'pending' ? 'warning' : 'danger'}>
                {payment.status}
              </Badge>
              <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-dark)' }}>
                {new Date(payment.timestamp).toLocaleTimeString()}
              </span>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  )
}

export default X402PaymentsPanel
