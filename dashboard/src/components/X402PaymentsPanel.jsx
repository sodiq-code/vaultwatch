/**
 * X402PaymentsPanel — Enhanced dual-path payment visualization with
 * Native CSPR + WCSPR (CEP-18) support and CSPR.cloud facilitator.
 *
 * Features:
 *   - Payment Path Selector (Native CSPR / WCSPR)
 *   - Dual Payment Flow Visualization
 *   - CSPR.cloud Facilitator Status
 *   - WCSPR Token Info
 *   - Enhanced Plans with dual pricing
 *   - Smart Contract dual entries
 *   - Recent Payments with path indicator
 */
import { useState, useEffect, useCallback } from 'react'
import { GlassCard } from '../ui/GlassCard.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { Badge, SourceBadge } from '../ui/Badge.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { SkeletonBlock, SkeletonLine } from '../ui/Skeleton.jsx'
import { CONTRACT_HASHES } from '../liveApi.js'

/* ─── Path selector tab styles ─── */
const PATH_TABS = [
  { key: 'native', label: 'Native CSPR', icon: '💎', color: 'var(--accent)' },
  { key: 'wcspr',  label: 'WCSPR (CEP-18)', icon: '🪙', color: 'var(--accent2)' },
]

/* ─── Flow steps per path ─── */
const NATIVE_FLOW = [
  { label: 'User Request',       icon: '👤', color: 'var(--accent)' },
  { label: 'x402 Interceptor',   icon: '🔒', color: 'var(--warning)' },
  { label: 'SubscriberVault.open_vault', icon: '🔓', color: 'var(--success)' },
  { label: 'CSPR Escrow Locked', icon: '📊', color: 'var(--accent)' },
  { label: 'Data Delivered',     icon: '✅', color: 'var(--success)' },
]

const WCSPR_FLOW = [
  { label: 'User Request',                        icon: '👤', color: 'var(--accent2)' },
  { label: 'x402 Interceptor',                    icon: '🔒', color: 'var(--warning)' },
  { label: 'CEP-18 transfer_with_authorization',  icon: '🔑', color: 'var(--accent2)' },
  { label: 'CSPR.cloud facilitator verify',       icon: '☁️', color: 'var(--accent3)' },
  { label: 'Data Delivered',                      icon: '✅', color: 'var(--success)' },
]

export function X402PaymentsPanel({ api, addToast }) {
  const [x402Status, setX402Status] = useState(null)
  const [facilitatorData, setFacilitatorData] = useState(null)
  const [wcsprData, setWCSPRData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [source, setSource] = useState(null)
  const [facilitatorSource, setFacilitatorSource] = useState(null)
  const [wcsprSource, setWCSPRSource] = useState(null)
  const [activePath, setActivePath] = useState('native')

  useEffect(() => {
    loadAll()
    const interval = setInterval(loadAll, 20000)
    return () => clearInterval(interval)
  }, [])

  const loadAll = useCallback(async () => {
    const promises = [loadStatus(), loadFacilitator(), loadWCSPR()]
    await Promise.allSettled(promises)
    setLoading(false)
  }, [])

  const loadStatus = async () => {
    try {
      const data = await api.getX402Status()
      if (data) {
        setX402Status(data)
        setSource(data._source || 'fallback')
      }
    } catch {
      // Keep stale data
    }
  }

  const loadFacilitator = async () => {
    try {
      const data = await api.getFacilitatorStatus()
      if (data) {
        setFacilitatorData(data)
        setFacilitatorSource(data._source || 'fallback')
      }
    } catch {
      // Keep stale
    }
  }

  const loadWCSPR = async () => {
    try {
      const data = await api.getWCSPRInfo()
      if (data) {
        setWCSPRData(data)
        setWCSPRSource(data._source || 'fallback')
      }
    } catch {
      // Keep stale
    }
  }

  /* ─── Loading state ─── */
  if (loading) {
    return (
      <div style={{ padding: 'var(--space-lg)' }}>
        <SkeletonBlock height={40} style={{ marginBottom: 'var(--space-lg)' }} />
        <SkeletonBlock height={300} style={{ marginBottom: 'var(--space-md)' }} />
        <SkeletonBlock height={200} />
      </div>
    )
  }

  /* ─── Error state ─── */
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
  const facilitator = facilitatorData?.facilitator || null
  const wcspr = wcsprData?.wcspr || null

  /* ─── Compute flow steps based on active path ─── */
  const flowSteps = activePath === 'native' ? NATIVE_FLOW : WCSPR_FLOW

  /* ─── Compute stat count ─── */
  const nativePayments = payments.filter(p => (p.paymentPath || 'native') === 'native')
  const wcsprPayments = payments.filter(p => p.paymentPath === 'wcspr')

  return (
    <div className="fade-in" style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="x402 Payments"
        subtitle="Dual-path CSPR + WCSPR (CEP-18) payment flow & facilitator status"
        icon="💰"
        source={source}
      />

      {/* ─── Stats ─── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 'var(--space-md)',
        marginBottom: 'var(--space-lg)',
      }}>
        <StatCard label="x402 Version" value={x402Status.x402Version || '—'} icon="📦" color="var(--accent)" animated={false} />
        <StatCard label="Scheme" value={x402Status.scheme || 'exact'} icon="⚙️" color="var(--accent2)" animated={false} />
        <StatCard label="Network" value={x402Status.network || 'casper-test'} icon="🔗" color="var(--success)" animated={false} />
        <StatCard label="Total Payments" value={payments.length} icon="💳" color="var(--warning)" />
        <StatCard label="Native CSPR" value={nativePayments.length} icon="💎" color="var(--accent)" animated={false} />
        <StatCard label="WCSPR" value={wcsprPayments.length} icon="🪙" color="var(--accent2)" animated={false} />
      </div>

      {/* ─── Payment Path Selector ─── */}
      <GlassCard hover={false} style={{ padding: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        <div style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-semibold)',
          color: 'var(--text)',
          marginBottom: 'var(--space-md)',
        }}>
          Payment Path
        </div>

        {/* Tab bar */}
        <div style={{
          display: 'flex',
          gap: 'var(--space-sm)',
          marginBottom: 'var(--space-lg)',
        }}>
          {PATH_TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActivePath(tab.key)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 20px',
                borderRadius: 'var(--radius-md)',
                fontSize: 'var(--font-size-md)',
                fontWeight: activePath === tab.key ? 'var(--font-weight-bold)' : 'var(--font-weight-medium)',
                color: activePath === tab.key ? tab.color : 'var(--text-muted)',
                background: activePath === tab.key
                  ? (tab.key === 'native' ? 'rgba(0, 212, 255, 0.12)' : 'rgba(139, 92, 246, 0.12)')
                  : 'rgba(14, 18, 30, 0.4)',
                border: `1px solid ${activePath === tab.key
                  ? (tab.key === 'native' ? 'rgba(0, 212, 255, 0.35)' : 'rgba(139, 92, 246, 0.35)')
                  : 'var(--border)'}`,
                cursor: 'pointer',
                transition: 'all var(--transition-normal)',
              }}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Dual flow visualization */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 'var(--space-lg)',
        }}>
          {/* Path A: Native CSPR */}
          <div style={{
            padding: 'var(--space-md)',
            background: activePath === 'native' ? 'rgba(0, 212, 255, 0.06)' : 'rgba(0, 212, 255, 0.02)',
            border: `1px solid ${activePath === 'native' ? 'rgba(0, 212, 255, 0.2)' : 'rgba(0, 212, 255, 0.08)'}`,
            borderRadius: 'var(--radius-lg)',
            opacity: activePath === 'native' ? 1 : 0.6,
            transition: 'all var(--transition-normal)',
          }}>
            <div style={{
              fontSize: 'var(--font-size-sm)',
              fontWeight: 'var(--font-weight-bold)',
              color: 'var(--accent)',
              textTransform: 'uppercase',
              letterSpacing: '1px',
              marginBottom: 'var(--space-sm)',
            }}>
              Path A — Native CSPR
            </div>
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-sm)',
            }}>
              {NATIVE_FLOW.map((step, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)',
                  padding: '6px 10px',
                  background: 'rgba(14, 18, 30, 0.5)',
                  borderRadius: 'var(--radius-sm)',
                }}>
                  <span style={{ fontSize: 14 }}>{step.icon}</span>
                  <span style={{
                    fontSize: 'var(--font-size-xs)',
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

            {/* Self-hosted badge */}
            <div style={{ marginTop: 'var(--space-sm)', display: 'flex', gap: 'var(--space-xs)' }}>
              <Badge size="xs" colorScheme="accent" icon="🏠">Self-Hosted</Badge>
              <Badge size="xs" colorScheme="success" icon="✓">SubscriberVault</Badge>
            </div>
          </div>

          {/* Path B: WCSPR */}
          <div style={{
            padding: 'var(--space-md)',
            background: activePath === 'wcspr' ? 'rgba(139, 92, 246, 0.06)' : 'rgba(139, 92, 246, 0.02)',
            border: `1px solid ${activePath === 'wcspr' ? 'rgba(139, 92, 246, 0.2)' : 'rgba(139, 92, 246, 0.08)'}`,
            borderRadius: 'var(--radius-lg)',
            opacity: activePath === 'wcspr' ? 1 : 0.6,
            transition: 'all var(--transition-normal)',
          }}>
            <div style={{
              fontSize: 'var(--font-size-sm)',
              fontWeight: 'var(--font-weight-bold)',
              color: 'var(--accent2)',
              textTransform: 'uppercase',
              letterSpacing: '1px',
              marginBottom: 'var(--space-sm)',
            }}>
              Path B — WCSPR (CEP-18)
            </div>
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-sm)',
            }}>
              {WCSPR_FLOW.map((step, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)',
                  padding: '6px 10px',
                  background: 'rgba(14, 18, 30, 0.5)',
                  borderRadius: 'var(--radius-sm)',
                }}>
                  <span style={{ fontSize: 14 }}>{step.icon}</span>
                  <span style={{
                    fontSize: 'var(--font-size-xs)',
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

            {/* CSPR.cloud facilitator badge */}
            <div style={{ marginTop: 'var(--space-sm)', display: 'flex', gap: 'var(--space-xs)' }}>
              <Badge size="xs" colorScheme="violet" icon="☁️">CSPR.cloud</Badge>
              <Badge size="xs" colorScheme="accent" icon="🔑">EIP-712 Sig</Badge>
            </div>
          </div>
        </div>

        {/* Helper / signer / facilitator availability */}
        <div style={{
          marginTop: 'var(--space-md)',
          display: 'flex',
          gap: 'var(--space-sm)',
          flexWrap: 'wrap',
        }}>
          <Badge colorScheme={x402Status.helperAvailable ? 'success' : 'danger'} size="sm" icon={x402Status.helperAvailable ? '✓' : '✕'}>
            Helper Available
          </Badge>
          <Badge colorScheme={x402Status.signerAvailable ? 'success' : 'danger'} size="sm" icon={x402Status.signerAvailable ? '✓' : '✕'}>
            Signer Available
          </Badge>
          <Badge colorScheme={facilitator?.status === 'configured' ? 'success' : 'warning'} size="sm" icon={facilitator?.status === 'configured' ? '✓' : '⚠'}>
            Facilitator {facilitator?.status || 'Unknown'}
          </Badge>
          <Badge colorScheme={facilitator?.reachable ? 'success' : 'danger'} size="sm" icon={facilitator?.reachable ? '✓' : '✕'}>
            CSPR.cloud Reachable
          </Badge>
        </div>
      </GlassCard>

      {/* ─── CSPR.cloud Facilitator Status ─── */}
      <GlassCard hover={false} style={{ padding: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 'var(--space-md)',
        }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
          }}>
            CSPR.cloud Facilitator
          </div>
          <SourceBadge source={facilitatorSource} />
        </div>

        {facilitator ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            {/* Endpoints */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 'var(--space-sm)',
            }}>
              {facilitator.endpoints.map(ep => (
                <div key={ep} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: 'var(--space-sm) var(--space-md)',
                  background: 'rgba(139, 92, 246, 0.08)',
                  border: '1px solid rgba(139, 92, 246, 0.15)',
                  borderRadius: 'var(--radius-md)',
                }}>
                  <span style={{
                    fontSize: 14,
                    color: facilitator.reachable ? 'var(--success)' : 'var(--danger)',
                  }}>
                    {facilitator.reachable ? '●' : '○'}
                  </span>
                  <span style={{
                    fontSize: 'var(--font-size-sm)',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--accent2)',
                  }}>
                    {ep}
                  </span>
                </div>
              ))}
            </div>

            {/* Config details */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 'var(--space-sm)',
              padding: 'var(--space-md)',
              background: 'rgba(14, 18, 30, 0.4)',
              borderRadius: 'var(--radius-md)',
              fontSize: 'var(--font-size-sm)',
            }}>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Base URL</span>
                <div style={{ color: 'var(--accent2)', fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}>
                  {facilitator.baseUrl}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Auth Method</span>
                <div style={{ color: 'var(--warning)', fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}>
                  {facilitator.authMethod}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Scheme</span>
                <div style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}>
                  {facilitator.scheme}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Network</span>
                <div style={{ color: 'var(--text)', fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}>
                  {facilitator.network}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Supported Tokens</span>
                <div style={{ display: 'flex', gap: 'var(--space-xs)', marginTop: 2 }}>
                  {facilitator.supportedTokens.map(tok => (
                    <Badge key={tok} size="xs" colorScheme="violet">{tok}</Badge>
                  ))}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Last Checked</span>
                <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-size-xs)' }}>
                  {facilitator.lastChecked ? new Date(facilitator.lastChecked).toLocaleTimeString() : '—'}
                </div>
              </div>
            </div>

            {/* Verification paths comparison */}
            <div style={{
              padding: 'var(--space-sm)',
              background: 'rgba(0, 212, 255, 0.04)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 'var(--font-size-xs)',
            }}>
              <div style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--text-secondary)', marginBottom: 4 }}>
                Dual Verification Paths
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-sm)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--accent)' }}>
                  <span>🏠</span>
                  <span>Self-hosted: SubscriberVault.open_vault → on-chain escrow</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--accent2)' }}>
                  <span>☁️</span>
                  <span>CSPR.cloud: CEP-18 transfer → /verify → /settle</span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{
            padding: 'var(--space-lg)',
            textAlign: 'center',
            color: 'var(--text-muted)',
            fontSize: 'var(--font-size-sm)',
          }}>
            Facilitator data unavailable
          </div>
        )}
      </GlassCard>

      {/* ─── WCSPR Token Info ─── */}
      <GlassCard hover={false} style={{ padding: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 'var(--space-md)',
        }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
          }}>
            WCSPR Token Info
          </div>
          <SourceBadge source={wcsprSource} />
        </div>

        {wcspr ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            {/* Token details grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: 'var(--space-sm)',
            }}>
              <div style={{
                padding: 'var(--space-md)',
                background: 'rgba(139, 92, 246, 0.08)',
                border: '1px solid rgba(139, 92, 246, 0.15)',
                borderRadius: 'var(--radius-md)',
              }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Name</span>
                <div style={{ color: 'var(--text)', fontWeight: 'var(--font-weight-semibold)', fontSize: 'var(--font-size-md)' }}>
                  {wcspr.name}
                </div>
              </div>
              <div style={{
                padding: 'var(--space-md)',
                background: 'rgba(139, 92, 246, 0.08)',
                border: '1px solid rgba(139, 92, 246, 0.15)',
                borderRadius: 'var(--radius-md)',
              }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Symbol</span>
                <div style={{ color: 'var(--accent2)', fontWeight: 'var(--font-weight-bold)', fontSize: 'var(--font-size-md)' }}>
                  {wcspr.symbol}
                </div>
              </div>
              <div style={{
                padding: 'var(--space-md)',
                background: 'rgba(139, 92, 246, 0.08)',
                border: '1px solid rgba(139, 92, 246, 0.15)',
                borderRadius: 'var(--radius-md)',
              }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Standard</span>
                <div style={{ color: 'var(--accent)', fontWeight: 'var(--font-weight-semibold)', fontSize: 'var(--font-size-md)' }}>
                  {wcspr.standard}
                </div>
              </div>
              <div style={{
                padding: 'var(--space-md)',
                background: 'rgba(139, 92, 246, 0.08)',
                border: '1px solid rgba(139, 92, 246, 0.15)',
                borderRadius: 'var(--radius-md)',
              }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Decimals</span>
                <div style={{ color: 'var(--text)', fontWeight: 'var(--font-weight-semibold)', fontSize: 'var(--font-size-md)' }}>
                  {wcspr.decimals}
                </div>
              </div>
              <div style={{
                padding: 'var(--space-md)',
                background: 'rgba(139, 92, 246, 0.08)',
                border: '1px solid rgba(139, 92, 246, 0.15)',
                borderRadius: 'var(--radius-md)',
              }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Price Ratio</span>
                <div style={{ color: 'var(--success)', fontWeight: 'var(--font-weight-semibold)', fontSize: 'var(--font-size-md)' }}>
                  {wcspr.price}
                </div>
              </div>
              <div style={{
                padding: 'var(--space-md)',
                background: 'rgba(139, 92, 246, 0.08)',
                border: '1px solid rgba(139, 92, 246, 0.15)',
                borderRadius: 'var(--radius-md)',
              }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Wallet Balance</span>
                <div style={{ color: wcspr.balance ? 'var(--text)' : 'var(--text-muted)', fontWeight: 'var(--font-weight-semibold)', fontSize: 'var(--font-size-md)' }}>
                  {wcspr.balance ?? 'Connect Wallet'}
                </div>
              </div>
            </div>

            {/* Contract hash & swap link */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 'var(--space-md)',
              padding: 'var(--space-md)',
              background: 'rgba(14, 18, 30, 0.4)',
              borderRadius: 'var(--radius-md)',
            }}>
              <div style={{ flex: 1 }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Contract Hash</span>
                <div style={{
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--accent2)',
                  fontFamily: 'var(--font-mono)',
                  wordBreak: 'break-all',
                }}>
                  {wcspr.contractHash?.slice(0, 20)}…{wcspr.contractHash?.slice(-12)}
                </div>
              </div>
              <GradientBtn
                variant="secondary"
                size="sm"
                icon="🔄"
                onClick={() => {
                  window.open(wcspr.swapUrl, '_blank', 'noopener')
                  if (addToast) addToast('Opening WCSPR swap on testnet.cspr.trade…', 'info')
                }}
              >
                Swap WCSPR
              </GradientBtn>
            </div>

            {/* Total supply */}
            {wcspr.totalSupply && (
              <div style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
              }}>
                Total Supply: {wcspr.totalSupply}
              </div>
            )}
          </div>
        ) : (
          <div style={{
            padding: 'var(--space-lg)',
            textAlign: 'center',
            color: 'var(--text-muted)',
            fontSize: 'var(--font-size-sm)',
          }}>
            WCSPR data unavailable
          </div>
        )}
      </GlassCard>

      {/* ─── Two column: Plans + SDK ─── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--space-lg)',
        marginBottom: 'var(--space-lg)',
      }}>
        {/* Enhanced plan pricing */}
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

                {/* Dual pricing display */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: 'var(--space-sm)',
                }}>
                  {/* Native CSPR price */}
                  <div style={{
                    padding: 'var(--space-sm)',
                    background: 'rgba(0, 212, 255, 0.08)',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid rgba(0, 212, 255, 0.15)',
                  }}>
                    <div style={{
                      fontSize: 'var(--font-size-xs)',
                      color: 'var(--text-muted)',
                      marginBottom: 2,
                    }}>
                      Native CSPR
                    </div>
                    <div style={{
                      fontSize: 'var(--font-size-xl)',
                      fontWeight: 'var(--font-weight-bold)',
                      color: 'var(--accent)',
                      lineHeight: 1,
                    }}>
                      {planData.amount_cspr} CSPR
                    </div>
                    <div style={{
                      fontSize: 'var(--font-size-xs)',
                      color: 'var(--text-muted)',
                      fontFamily: 'var(--font-mono)',
                      marginTop: 2,
                    }}>
                      {planData.amount_motes?.toLocaleString()} motes
                    </div>
                  </div>

                  {/* WCSPR price */}
                  <div style={{
                    padding: 'var(--space-sm)',
                    background: 'rgba(139, 92, 246, 0.08)',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid rgba(139, 92, 246, 0.15)',
                  }}>
                    <div style={{
                      fontSize: 'var(--font-size-xs)',
                      color: 'var(--text-muted)',
                      marginBottom: 2,
                    }}>
                      WCSPR (CEP-18)
                    </div>
                    <div style={{
                      fontSize: 'var(--font-size-xl)',
                      fontWeight: 'var(--font-weight-bold)',
                      color: 'var(--accent2)',
                      lineHeight: 1,
                    }}>
                      {planData.amount_wcspr ?? planData.amount_cspr} WCSPR
                    </div>
                    <div style={{
                      fontSize: 'var(--font-size-xs)',
                      color: 'var(--text-muted)',
                      fontFamily: 'var(--font-mono)',
                      marginTop: 2,
                    }}>
                      CEP-18 transfer_with_auth
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* SDK info */}
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
            marginBottom: 'var(--space-md)',
          }}>
            SDK Dependencies
          </div>

          <div style={{
            padding: 'var(--space-md)',
            background: 'rgba(14, 18, 30, 0.4)',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--font-size-sm)',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-sm)',
          }}>
            {Object.entries(sdkInfo).map(([pkg, ver]) => (
              <div key={pkg} style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 10px',
                background: 'rgba(14, 18, 30, 0.5)',
                borderRadius: 'var(--radius-sm)',
              }}>
                <span style={{ color: 'var(--text-secondary)', fontWeight: 'var(--font-weight-medium)' }}>{pkg}</span>
                <Badge size="xs" colorScheme="accent">{ver}</Badge>
              </div>
            ))}
          </div>

          {/* x402 protocol details */}
          <div style={{
            marginTop: 'var(--space-md)',
            padding: 'var(--space-md)',
            background: 'rgba(0, 212, 255, 0.04)',
            borderRadius: 'var(--radius-md)',
          }}>
            <div style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)', fontSize: 'var(--font-size-sm)' }}>
              Protocol Configuration
            </div>
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-xs)',
              fontSize: 'var(--font-size-xs)',
              fontFamily: 'var(--font-mono)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Scheme</span>
                <span style={{ color: 'var(--accent)' }}>{x402Status.scheme || 'exact'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Network</span>
                <span style={{ color: 'var(--success)' }}>{x402Status.network || 'casper:casper-test'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Version</span>
                <span style={{ color: 'var(--text)' }}>{x402Status.x402Version || '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Payment Paths</span>
                <span style={{ color: 'var(--accent2)' }}>2 (CSPR + WCSPR)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Facilitator</span>
                <span style={{ color: facilitator?.status === 'configured' ? 'var(--success)' : 'var(--warning)' }}>
                  {facilitator?.status === 'configured' ? '✓ CSPR.cloud' : '⚠ Unconfigured'}
                </span>
              </div>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* ─── Smart Contracts (dual entries) ─── */}
      <GlassCard hover={false} style={{ padding: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        <div style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-semibold)',
          color: 'var(--text)',
          marginBottom: 'var(--space-md)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-sm)',
        }}>
          Smart Contracts
          <Badge size="sm" colorScheme="accent">{Object.keys(contracts).length}</Badge>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {Object.entries(contracts).map(([name, info]) => (
            <div key={name} className="glass-row-hover" style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-md)',
              padding: 'var(--space-md)',
              background: info.path === 'wcspr'
                ? 'rgba(139, 92, 246, 0.06)'
                : 'rgba(0, 212, 255, 0.04)',
              border: `1px solid ${info.path === 'wcspr'
                ? 'rgba(139, 92, 246, 0.1)'
                : 'rgba(0, 212, 255, 0.06)'}`,
              borderRadius: 'var(--radius-md)',
            }}>
              {/* Path badge */}
              <Badge size="sm" colorScheme={info.path === 'wcspr' ? 'violet' : 'accent'}>
                {info.path === 'wcspr' ? '🪙 WCSPR' : '💎 Native'}
              </Badge>

              {/* Contract name */}
              <div style={{
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-semibold)',
                color: info.path === 'wcspr' ? 'var(--accent2)' : 'var(--accent)',
                minWidth: 100,
              }}>
                {name}
              </div>

              {/* Contract hash */}
              <div style={{
                flex: 1,
                fontSize: 'var(--font-size-sm)',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                wordBreak: 'break-all',
              }}>
                {info.contractHash?.slice(0, 16)}…{info.contractHash?.slice(-8)}
              </div>

              {/* Entry point */}
              <Badge size="xs" colorScheme={info.path === 'wcspr' ? 'violet' : 'muted'}>
                {info.entryPoint}
              </Badge>

              {/* Label */}
              {info.label && (
                <span style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-dark)',
                  fontStyle: 'italic',
                }}>
                  {info.label}
                </span>
              )}

              <SourceBadge source={source} />
            </div>
          ))}
        </div>

        {/* Deployer account */}
        <div style={{
          marginTop: 'var(--space-sm)',
          padding: 'var(--space-sm)',
          background: 'rgba(14, 18, 30, 0.3)',
          borderRadius: 'var(--radius-sm)',
          fontSize: 'var(--font-size-xs)',
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-muted)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <span style={{ color: 'var(--text-secondary)' }}>Deployer:</span>
          <span style={{ color: 'var(--accent)' }}>
            0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7
          </span>
        </div>
      </GlassCard>

      {/* ─── Recent Payments (with path indicator) ─── */}
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

        {/* Path filter summary */}
        <div style={{
          display: 'flex',
          gap: 'var(--space-sm)',
          marginBottom: 'var(--space-md)',
        }}>
          <Badge size="sm" colorScheme="accent" icon="💎">
            {nativePayments.length} Native CSPR
          </Badge>
          <Badge size="sm" colorScheme="violet" icon="🪙">
            {wcsprPayments.length} WCSPR
          </Badge>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {payments.map((payment, i) => {
            const isWCSPR = payment.paymentPath === 'wcspr'
            const amountDisplay = isWCSPR
              ? `${payment.amount_wcspr ?? payment.amount_cspr} WCSPR`
              : `${payment.amount_cspr} CSPR`

            return (
              <div key={payment.id || i} className="glass-row-hover" style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                padding: 'var(--space-md)',
                background: isWCSPR
                  ? 'rgba(139, 92, 246, 0.04)'
                  : 'rgba(0, 212, 255, 0.04)',
                border: `1px solid ${isWCSPR
                  ? 'rgba(139, 92, 246, 0.1)'
                  : 'rgba(0, 212, 255, 0.08)'}`,
                borderRadius: 'var(--radius-md)',
              }}>
                {/* Path badge */}
                <Badge size="sm" colorScheme={isWCSPR ? 'violet' : 'accent'} icon={isWCSPR ? '🪙' : '💎'}>
                  {isWCSPR ? 'WCSPR' : 'Native'}
                </Badge>

                {/* Plan */}
                <Badge size="sm" colorScheme={payment.plan === 'premium' ? 'violet' : 'accent'}>
                  {payment.plan}
                </Badge>

                {/* Amount */}
                <div style={{
                  fontSize: 'var(--font-size-sm)',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: isWCSPR ? 'var(--accent2)' : 'var(--accent)',
                }}>
                  {amountDisplay}
                </div>

                {/* Subscriber */}
                <div style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                }}>
                  {payment.subscriber?.slice(0, 10)}…
                </div>

                {/* Deploy hash */}
                <div style={{
                  flex: 1,
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-dark)',
                  fontFamily: 'var(--font-mono)',
                }}>
                  {payment.deploy_hash?.slice(0, 12)}…
                </div>

                {/* Status */}
                <Badge size="xs" colorScheme={
                  payment.status === 'verified' ? 'success'
                  : payment.status === 'pending' ? 'warning'
                  : 'danger'
                }>
                  {payment.status}
                </Badge>

                {/* Timestamp */}
                <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-dark)' }}>
                  {new Date(payment.timestamp).toLocaleTimeString()}
                </span>
              </div>
            )
          })}
        </div>
      </GlassCard>
    </div>
  )
}

export default X402PaymentsPanel
