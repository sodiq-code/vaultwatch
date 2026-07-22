import { useState, useEffect, useCallback } from 'react'
import {
  CONTRACT_HASHES,
  DEPLOYER_ACCOUNT,
  getLiveBlockHeight,
  fetchCSPRPrice,
  fetchNetworkInfo,
  fetchAccountDeploys,
  fetchCSPRPriceHistory,
} from '../liveApi.js'
import { GlassCard } from '../ui/GlassCard.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { SkeletonCard, SkeletonLine, SkeletonTable } from '../ui/Skeleton.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { Input } from '../ui/Input.jsx'
import { Badge, SourceBadge } from '../ui/Badge.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { AnimatedCounter } from '../ui/AnimatedCounter.jsx'
import { CSPRPriceChart } from '../charts/CSPRPriceChart.jsx'
import { LatencyChart } from '../charts/LatencyChart.jsx'

const CONTRACT_EXPLORER = 'https://testnet.cspr.live/deploy/'
const ACCOUNT_EXPLORER  = 'https://testnet.cspr.live/account/'

const CONTRACT_ROLES = [
  { name: 'AuditTrail',         role: 'Immutable agent action log' },
  { name: 'RiskOracle',         role: 'Risk scores queryable by any dApp' },
  { name: 'SentinelCredit',     role: 'x402 credit ledger for pay-per-query' },
  { name: 'SentinelRegistry',   role: 'Subscriber registry for push alerts' },
  { name: 'SentinelAlertLog',   role: 'Timestamped alert history' },
  { name: 'AgentBehaviorIndex', role: 'AI agent performance on-chain' },
  { name: 'RiskPolicyManager',  role: 'Hot-swappable risk thresholds' },
  { name: 'SubscriberVault',    role: 'Escrowed prepay balance' },
]

export default function ChainStatus({ api, addToast }) {
  const [blockHeight, setBlockHeight]     = useState(getLiveBlockHeight())
  const [spans, setSpans]                 = useState([])
  const [cspr, setCspr]                   = useState(null)
  const [network, setNetwork]             = useState(null)
  const [deploys, setDeploys]             = useState([])
  const [priceHistory, setPriceHistory]   = useState([])
  const [loading, setLoading]             = useState(false)
  const [lastRefreshed, setLastRefreshed] = useState(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [spansData, price, netInfo, accountDeploys, hist] = await Promise.allSettled([
        api.getSpans().catch(() => ({ spans: [] })),
        fetchCSPRPrice(),
        fetchNetworkInfo(),
        fetchAccountDeploys(32),
        fetchCSPRPriceHistory(),
      ])
      if (spansData.status === 'fulfilled') setSpans(spansData.value?.spans || [])
      if (price.status === 'fulfilled') setCspr(price.value)
      if (netInfo.status === 'fulfilled') setNetwork(netInfo.value)
      if (accountDeploys.status === 'fulfilled') setDeploys(accountDeploys.value || [])
      if (hist.status === 'fulfilled') setPriceHistory(hist.value || [])
      setBlockHeight(getLiveBlockHeight())
      setLastRefreshed(new Date())
    } catch (e) {
      if (addToast) addToast({ type: 'error', message: `Chain refresh failed: ${e.message}` })
    } finally {
      setLoading(false)
    }
  }, [api, addToast])

  useEffect(() => {
    refresh()
    const blockTick   = setInterval(() => setBlockHeight(getLiveBlockHeight()), 10_000)
    const fullRefresh = setInterval(refresh, 30_000)
    return () => { clearInterval(blockTick); clearInterval(fullRefresh) }
  }, [refresh])

  const priceColor  = !cspr?.change_24h ? 'accent' : cspr.change_24h >= 0 ? 'success' : 'danger'
  const priceChange = cspr?.change_24h != null
    ? `${cspr.change_24h >= 0 ? '+' : ''}${cspr.change_24h.toFixed(2)}% 24h`
    : null

  const fmtMotes = (m) => {
    if (!m) return '—'
    const cspr = Number(m) / 1e9
    return cspr >= 1 ? `${cspr.toFixed(2)} CSPR` : `${Number(m).toLocaleString()} motes`
  }

  const fmtTime = (ts) => {
    if (!ts) return '—'
    const d = new Date(ts)
    return isNaN(d) ? ts : d.toLocaleString()
  }

  // Build LatencyChart data from spans
  const latencyData = spans.slice(-20).reverse().map(s => ({
    name: s.name,
    spanId: s.span_id || s.name,
    durationMs: s.duration_ms || 0,
    status: s.status || 'OK',
    color: s.duration_ms < 500 ? '#22c55e'
      : s.duration_ms < 1500 ? '#3b82f6'
      : '#f59e0b',
  }))

  return (
    <div>
      <PageHeader
        icon="🔗"
        badge="ON-CHAIN"
        title="Chain Status"
        subtitle={
          <>
            Live Casper testnet block data, CSPR market price, deployed Odra contracts, and OTel agent traces.
            {lastRefreshed && (
              <span style={{ marginLeft: 8, fontSize: 'var(--font-size-xs)' }}>
                Last refreshed: {lastRefreshed.toLocaleTimeString()}
              </span>
            )}
          </>
        }
      />

      {/* ── Live Network Overview ─────────────────────────────────────────── */}
      <GlassCard>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
          <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)' }}>
            Live Network Overview · casper-test
          </h2>
          <GradientBtn
            variant="ghost"
            size="sm"
            onClick={refresh}
            disabled={loading}
            loading={loading}
          >
            {loading ? 'Refreshing…' : '↺ Refresh'}
          </GradientBtn>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(155px, 1fr))', gap: 'var(--space-sm)' }}>
          <StatCard
            label="Block Height"
            value={network?.block_height ? network.block_height.toLocaleString() : blockHeight.toLocaleString()}
            sub={network?.block_height ? '✓ from cspr.cloud' : '~1 block / 65s'}
            color="accent"
            icon="⬡"
          />
          <StatCard
            label="Era ID"
            value={network?.era_id ?? '—'}
            sub={network?.timestamp ? `Block: ${new Date(network.timestamp).toLocaleTimeString()}` : 'casper-test'}
            color="accent"
            icon="⚡"
          />
          <StatCard
            label="CSPR Price (USD)"
            value={cspr?.usd != null ? `$${cspr.usd.toFixed(4)}` : 'Loading…'}
            sub={priceChange ?? 'CoinGecko live'}
            color={priceColor}
            icon="💲"
          />
          <StatCard
            label="Market Cap"
            value={cspr?.market_cap ? `$${(cspr.market_cap / 1e6).toFixed(1)}M` : '—'}
            sub="CoinGecko"
            icon="📈"
          />
          <StatCard
            label="24h Volume"
            value={cspr?.vol_24h ? `$${(cspr.vol_24h / 1e6).toFixed(2)}M` : '—'}
            sub="CoinGecko"
            icon="📊"
          />
          <StatCard
            label="Contracts Deployed"
            value={`${Object.keys(CONTRACT_HASHES).length} / 8`}
            sub="Odra WASM · casper-test"
            color="success"
            icon="⬡"
          />
        </div>

        {/* Latest block metadata */}
        {network && (
          <GlassCard style={{ marginTop: 'var(--space-md)', padding: 'var(--space-md)' }}>
            <div style={{ color: 'var(--text-muted)', marginBottom: 'var(--space-sm)', fontWeight: 'var(--font-weight-semibold)', textTransform: 'uppercase', fontSize: 'var(--font-size-xs)', letterSpacing: 1 }}>
              Latest Block Details
            </div>
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 'var(--font-size-xs)' }}>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Block hash: </span>
                <a href={`https://testnet.cspr.live/block/${network.block_hash}`} target="_blank" rel="noopener noreferrer"
                  style={{ color: 'var(--accent)', fontFamily: 'var(--font)', fontSize: 'var(--font-size-xs)', textDecoration: 'none' }}>
                  {network.block_hash ? network.block_hash.slice(0, 24) + '…' : '—'} ↗
                </a>
              </div>
              {network.validator && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Proposer: </span>
                  <span style={{ fontFamily: 'var(--font)', fontSize: 'var(--font-size-xs)' }}>{network.validator}</span>
                </div>
              )}
              {network.tx_count !== undefined && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Deploys: </span>
                  <span style={{ fontWeight: 'var(--font-weight-semibold)' }}>{network.tx_count}</span>
                </div>
              )}
              {network.timestamp && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Time: </span>
                  <span>{new Date(network.timestamp).toUTCString()}</span>
                </div>
              )}
            </div>
          </GlassCard>
        )}
      </GlassCard>

      {/* ── CSPR Price Chart ──────────────────────────────────────────────── */}
      {priceHistory.length > 0 && (
        <GlassCard>
          <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-md)' }}>
            CSPR / USD · 7-Day Price (CoinGecko Live)
          </h2>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 24, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 32, fontWeight: 'var(--font-weight-bold)',
                color: cspr?.change_24h >= 0 ? 'var(--success)' : cspr?.change_24h < 0 ? 'var(--danger)' : 'var(--text)' }}>
                <AnimatedCounter
                  value={cspr?.usd ?? 0}
                  formatter={v => `$${v.toFixed(4)}`}
                />
              </div>
              {priceChange && (
                <div style={{
                  color: cspr?.change_24h >= 0 ? 'var(--success)' : 'var(--danger)',
                  fontSize: 'var(--font-size-sm)', marginTop: 2,
                }}>
                  {priceChange}
                </div>
              )}
              <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)', marginTop: 4 }}>
                BTC: {cspr?.btc ? `₿${cspr.btc.toFixed(8)}` : '—'}
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <CSPRPriceChart data={priceHistory} height={120} />
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
                <span>7 days ago</span>
                <span>Today</span>
              </div>
            </div>
          </div>
        </GlassCard>
      )}

      {/* ── Deployer Account ─────────────────────────────────────────────── */}
      <GlassCard>
        <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-sm)' }}>
          Deployer Account · Casper Testnet
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)', marginBottom: 'var(--space-md)' }}>
          All 8 Odra contracts were deployed from this account on June 24, 2026.
        </p>
        <GlassCard style={{ padding: 'var(--space-md)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Public Key:</span>
            <code style={{ color: 'var(--accent)', wordBreak: 'break-all', fontSize: 'var(--font-size-xs)', flex: 1 }}>
              {DEPLOYER_ACCOUNT}
            </code>
            <a
              href={`${ACCOUNT_EXPLORER}${DEPLOYER_ACCOUNT}`}
              target="_blank" rel="noopener noreferrer"
              style={{
                color: '#fff', background: 'var(--gradient-accent)', padding: '4px 12px',
                borderRadius: 'var(--radius-md)', textDecoration: 'none', fontSize: 'var(--font-size-xs)', fontWeight: 'var(--font-weight-semibold)',
                flexShrink: 0,
              }}
            >
              View Account ↗
            </a>
          </div>
          <div style={{ marginTop: 'var(--space-md)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 'var(--space-sm)' }}>
            <StatCard
              label="Total Deploys"
              value={deploys.length || 32}
              color="accent"
              icon="📦"
            />
            <StatCard
              label="Contracts"
              value={8}
              color="success"
              icon="⬡"
            />
            <StatCard
              label="Network"
              value="casper-test"
              color="warning"
              icon="🔗"
            />
            <StatCard
              label="Deploy Date"
              value="Jun 24, 2026"
              icon="📅"
            />
          </div>
        </GlassCard>
      </GlassCard>

      {/* ── Deployed Contracts ────────────────────────────────────────────── */}
      <GlassCard>
        <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 6 }}>
          Deployed Odra Contracts · Casper Testnet
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)', marginBottom: 'var(--space-md)' }}>
          8 Odra WASM contracts deployed on casper-test. Each contract has a unique deploy hash — click any to verify on the Casper explorer.
        </p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--font-size-xs)' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>#</th>
                <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Contract</th>
                <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Role</th>
                <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Deploy Hash (casper-test)</th>
                <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {CONTRACT_ROLES.map(({ name, role }, i) => {
                const hash = CONTRACT_HASHES[name]
                return (
                  <tr key={name} className="glass-row-hover" style={{
                    borderBottom: '1px solid var(--border)',
                    transition: 'background var(--transition-normal)',
                  }}>
                    <td style={{ padding: 'var(--space-sm) var(--space-md)', color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>{i + 1}</td>
                    <td style={{ padding: 'var(--space-sm) var(--space-md)', color: 'var(--accent)', fontWeight: 'var(--font-weight-bold)' }}>{name}</td>
                    <td style={{ padding: 'var(--space-sm) var(--space-md)', color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)', maxWidth: 180 }}>{role}</td>
                    <td style={{ padding: 'var(--space-sm) var(--space-md)' }}>
                      <a
                        href={`${CONTRACT_EXPLORER}${hash}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={`Full hash: ${hash}`}
                        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font)', textDecoration: 'none', fontSize: 'var(--font-size-xs)' }}
                      >
                        {hash.slice(0, 18)}…{hash.slice(-6)} ↗
                      </a>
                    </td>
                    <td style={{ padding: 'var(--space-sm) var(--space-md)' }}>
                      <Badge variant="success" size="sm">✓ DEPLOYED</Badge>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: 'var(--space-md)', display: 'flex', gap: 'var(--space-sm)' }}>
          <a
            href={`${ACCOUNT_EXPLORER}${DEPLOYER_ACCOUNT}`}
            target="_blank" rel="noopener noreferrer"
            style={{ fontSize: 'var(--font-size-xs)', color: 'var(--accent)', textDecoration: 'none', padding: '6px 12px',
              background: 'var(--glass-bg)', borderRadius: 'var(--radius-md)', border: '1px solid var(--glass-border)' }}
          >
            ⬡ View All Deploys on Explorer ↗
          </a>
        </div>
      </GlassCard>

      {/* ── Recent Account Deploys ────────────────────────────────────────── */}
      {deploys.length > 0 && (
        <GlassCard>
          <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 6 }}>
            Recent Account Deploys
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', fontWeight: 'var(--font-weight-normal)', marginLeft: 8 }}>
              via cspr.cloud API
            </span>
          </h2>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--font-size-xs)' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Deploy Hash</th>
                  <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Contract</th>
                  <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Cost</th>
                  <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Time</th>
                  <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {deploys.slice(0, 15).map((d, i) => {
                  const hash = d.deploy_hash || d.deployHash
                  const contractName = d.contract || Object.entries(CONTRACT_HASHES).find(([, h]) => h === hash)?.[0] || '—'
                  const isSuccess = d.status === 'executed' || d.status === 'success'
                  return (
                    <tr key={i} className="glass-row-hover" style={{
                      borderBottom: '1px solid var(--border)',
                      transition: 'background var(--transition-normal)',
                    }}>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)' }}>
                        <a href={`${CONTRACT_EXPLORER}${hash}`} target="_blank" rel="noopener noreferrer"
                          style={{ color: 'var(--accent)', fontFamily: 'var(--font)', textDecoration: 'none', fontSize: 'var(--font-size-xs)' }}>
                          {hash ? hash.slice(0, 16) + '…' : '—'} ↗
                        </a>
                      </td>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)', color: contractName !== '—' ? 'var(--accent)' : 'var(--text-muted)', fontWeight: contractName !== '—' ? 'var(--font-weight-semibold)' : 'var(--font-weight-normal)' }}>
                        {contractName}
                      </td>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)', color: 'var(--text-muted)' }}>
                        {fmtMotes(d.cost)}
                      </td>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)', color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
                        {fmtTime(d.timestamp)}
                      </td>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)' }}>
                        <Badge variant={isSuccess ? 'success' : 'warning'} size="sm">
                          {d.status || 'executed'}
                        </Badge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      {/* ── OTel Spans ────────────────────────────────────────────────────── */}
      <GlassCard>
        <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-md)' }}>
          OTel Agent Traces ({spans.length} spans)
        </h2>
        {loading && spans.length === 0 ? (
          <SkeletonTable rows={5} cols={4} />
        ) : spans.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)' }}>
            No spans collected yet. Run a risk query or anomaly scan to generate traces.
          </p>
        ) : (
          <>
            <LatencyChart spans={latencyData} height={160} />
            <div style={{ overflowX: 'auto', marginTop: 'var(--space-md)' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--font-size-sm)' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                    <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Span</th>
                    <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Duration</th>
                    <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {spans.slice(-20).reverse().map((s, i) => (
                    <tr key={i} className="glass-row-hover" style={{
                      borderBottom: '1px solid var(--border)',
                      transition: 'background var(--transition-normal)',
                    }}>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)', color: 'var(--accent)', fontFamily: 'var(--font)', fontSize: 'var(--font-size-xs)' }}>{s.name}</td>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)', fontWeight: 'var(--font-weight-semibold)' }}>
                        <AnimatedCounter value={s.duration_ms ?? 0} formatter={v => `${v.toFixed(1)}ms`} />
                      </td>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)' }}>
                        <Badge variant={s.status === 'OK' ? 'success' : 'danger'} size="sm">{s.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </GlassCard>
    </div>
  )
}
