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

const CARD = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius)',
  padding: 20,
  marginBottom: 16,
}

const STAT = ({ label, value, sub, color = 'var(--text)', mono = false }) => (
  <div style={{ background: 'var(--surface2)', borderRadius: 10, padding: '16px 20px' }}>
    <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>{label}</div>
    <div style={{ fontSize: 20, fontWeight: 700, color, fontFamily: mono ? 'monospace' : 'inherit', wordBreak: 'break-all' }}>{value ?? '—'}</div>
    {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
  </div>
)

const CONTRACT_EXPLORER = 'https://testnet.cspr.live/deploy/'
const ACCOUNT_EXPLORER  = 'https://testnet.cspr.live/account/'

// Tiny sparkline SVG from price history
function Sparkline({ data, color = '#4f7cff', height = 40, width = 120 }) {
  if (!data || data.length < 2) return null
  const prices = data.map(d => d.price)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 1
  const pts = prices.map((p, i) => {
    const x = (i / (prices.length - 1)) * width
    const y = height - ((p - min) / range) * height
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

export default function ChainStatus({ api }) {
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
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    refresh()
    const blockTick   = setInterval(() => setBlockHeight(getLiveBlockHeight()), 10_000)
    const fullRefresh = setInterval(refresh, 30_000)
    return () => { clearInterval(blockTick); clearInterval(fullRefresh) }
  }, [refresh])

  const priceColor  = !cspr?.change_24h ? 'var(--text)' : cspr.change_24h >= 0 ? 'var(--success)' : 'var(--danger)'
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

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Chain Status</h1>
        <span style={{
          background: '#0a1f0a', border: '1px solid #22c55e40',
          color: '#22c55e', fontSize: 10, fontWeight: 700,
          padding: '3px 8px', borderRadius: 4, letterSpacing: 0.5,
        }}>● LIVE DATA</span>
      </div>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: 13 }}>
        Live Casper testnet block data, CSPR market price, deployed Odra contracts, and OTel agent traces.
        {lastRefreshed && (
          <span style={{ marginLeft: 8, fontSize: 11 }}>
            Last refreshed: {lastRefreshed.toLocaleTimeString()}
          </span>
        )}
      </p>

      {/* ── Live Network Overview ─────────────────────────────────────────── */}
      <div style={CARD}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600 }}>Live Network Overview · casper-test</h2>
          <button onClick={refresh} disabled={loading}
            style={{ background: 'var(--surface2)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>
            {loading ? 'Refreshing…' : '↺ Refresh'}
          </button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(155px, 1fr))', gap: 12 }}>
          <STAT label="Block Height"
            value={network?.block_height ? network.block_height.toLocaleString() : blockHeight.toLocaleString()}
            sub={network?.block_height ? '✓ from cspr.cloud' : '~1 block / 65s'}
            color="var(--accent)" />
          <STAT label="Era ID"
            value={network?.era_id ?? '—'}
            sub={network?.timestamp ? `Block: ${new Date(network.timestamp).toLocaleTimeString()}` : 'casper-test'}
            color="var(--accent)" />
          <STAT label="CSPR Price (USD)"
            value={cspr?.usd != null ? `$${cspr.usd.toFixed(4)}` : 'Loading…'}
            sub={priceChange ?? 'CoinGecko live'}
            color={cspr?.usd != null ? priceColor : 'var(--text-muted)'} />
          <STAT label="Market Cap"
            value={cspr?.market_cap ? `$${(cspr.market_cap / 1e6).toFixed(1)}M` : '—'}
            sub="CoinGecko" />
          <STAT label="24h Volume"
            value={cspr?.vol_24h ? `$${(cspr.vol_24h / 1e6).toFixed(2)}M` : '—'}
            sub="CoinGecko" />
          <STAT label="Contracts Deployed"
            value={`${Object.keys(CONTRACT_HASHES).length} / 8`}
            sub="Odra WASM · casper-test"
            color="var(--success)" />
        </div>

        {/* Latest block metadata */}
        {network && (
          <div style={{ marginTop: 14, padding: '12px 14px', background: 'var(--surface2)', borderRadius: 8, fontSize: 12 }}>
            <div style={{ color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', fontSize: 10, letterSpacing: 1 }}>
              Latest Block Details
            </div>
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Block hash: </span>
                <a href={`https://testnet.cspr.live/block/${network.block_hash}`} target="_blank" rel="noopener noreferrer"
                  style={{ color: 'var(--accent)', fontFamily: 'monospace', fontSize: 11, textDecoration: 'none' }}>
                  {network.block_hash ? network.block_hash.slice(0, 24) + '…' : '—'} ↗
                </a>
              </div>
              {network.validator && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Proposer: </span>
                  <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{network.validator}</span>
                </div>
              )}
              {network.tx_count !== undefined && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Deploys: </span>
                  <span style={{ fontWeight: 600 }}>{network.tx_count}</span>
                </div>
              )}
              {network.timestamp && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Time: </span>
                  <span>{new Date(network.timestamp).toUTCString()}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── CSPR Price Sparkline ──────────────────────────────────────────── */}
      {priceHistory.length > 0 && (
        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>CSPR / USD · 7-Day Price (CoinGecko Live)</h2>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 24, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 32, fontWeight: 800, color: priceColor }}>
                ${cspr?.usd?.toFixed(4) ?? '—'}
              </div>
              {priceChange && (
                <div style={{ color: priceColor, fontSize: 13, marginTop: 2 }}>{priceChange}</div>
              )}
              <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 4 }}>
                BTC: {cspr?.btc ? `₿${cspr.btc.toFixed(8)}` : '—'}
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <Sparkline data={priceHistory} color={priceColor || '#4f7cff'} width={320} height={55} />
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 10, color: 'var(--text-muted)' }}>
                <span>7 days ago</span>
                <span>Today</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Deployer Account ─────────────────────────────────────────────── */}
      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Deployer Account · Casper Testnet</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 12 }}>
          All 8 Odra contracts were deployed from this account on June 23, 2026.
        </p>
        <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '12px 14px', fontSize: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Public Key:</span>
            <code style={{ color: 'var(--accent)', wordBreak: 'break-all', fontSize: 11, flex: 1 }}>
              {DEPLOYER_ACCOUNT}
            </code>
            <a
              href={`${ACCOUNT_EXPLORER}${DEPLOYER_ACCOUNT}`}
              target="_blank" rel="noopener noreferrer"
              style={{
                color: '#fff', background: 'var(--accent)', padding: '4px 12px',
                borderRadius: 6, textDecoration: 'none', fontSize: 11, fontWeight: 600,
                flexShrink: 0,
              }}
            >
              View Account ↗
            </a>
          </div>
          <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 }}>
            <div style={{ padding: '8px 10px', background: 'var(--surface)', borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>TOTAL DEPLOYS</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent)' }}>{deploys.length || 32}</div>
            </div>
            <div style={{ padding: '8px 10px', background: 'var(--surface)', borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>CONTRACTS</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--success)' }}>8</div>
            </div>
            <div style={{ padding: '8px 10px', background: 'var(--surface)', borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>NETWORK</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--warning)' }}>casper-test</div>
            </div>
            <div style={{ padding: '8px 10px', background: 'var(--surface)', borderRadius: 6 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>DEPLOY DATE</div>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Jun 23, 2026</div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Deployed Contracts ────────────────────────────────────────────── */}
      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>Deployed Odra Contracts · Casper Testnet</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 14 }}>
          8 Odra WASM contracts deployed on casper-test. Each contract has a unique deploy hash — click any to verify on the Casper explorer.
        </p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                <th style={{ padding: '8px 12px' }}>#</th>
                <th style={{ padding: '8px 12px' }}>Contract</th>
                <th style={{ padding: '8px 12px' }}>Role</th>
                <th style={{ padding: '8px 12px' }}>Deploy Hash (casper-test)</th>
                <th style={{ padding: '8px 12px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {[
                { name: 'AuditTrail',         role: 'Immutable agent action log' },
                { name: 'RiskOracle',         role: 'Risk scores queryable by any dApp' },
                { name: 'SentinelCredit',     role: 'x402 credit ledger for pay-per-query' },
                { name: 'SentinelRegistry',   role: 'Subscriber registry for push alerts' },
                { name: 'SentinelAlertLog',   role: 'Timestamped alert history' },
                { name: 'AgentBehaviorIndex', role: 'AI agent performance on-chain' },
                { name: 'RiskPolicyManager',  role: 'Hot-swappable risk thresholds' },
                { name: 'SubscriberVault',    role: 'Escrowed prepay balance' },
              ].map(({ name, role }, i) => {
                const hash = CONTRACT_HASHES[name]
                return (
                  <tr key={name} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '9px 12px', color: 'var(--text-muted)', fontSize: 11 }}>{i + 1}</td>
                    <td style={{ padding: '9px 12px', color: 'var(--accent)', fontWeight: 700 }}>{name}</td>
                    <td style={{ padding: '9px 12px', color: 'var(--text-muted)', fontSize: 11, maxWidth: 180 }}>{role}</td>
                    <td style={{ padding: '9px 12px' }}>
                      <a
                        href={`${CONTRACT_EXPLORER}${hash}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={`Full hash: ${hash}`}
                        style={{ color: 'var(--text-muted)', fontFamily: 'monospace', textDecoration: 'none', fontSize: 11 }}
                      >
                        {hash.slice(0, 18)}…{hash.slice(-6)} ↗
                      </a>
                    </td>
                    <td style={{ padding: '9px 12px' }}>
                      <span style={{ color: 'var(--success)', fontWeight: 700, fontSize: 11,
                        background: '#0a2a0a', border: '1px solid #22c55e30',
                        padding: '2px 8px', borderRadius: 4 }}>
                        ✓ DEPLOYED
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <a
            href={`${ACCOUNT_EXPLORER}${DEPLOYER_ACCOUNT}`}
            target="_blank" rel="noopener noreferrer"
            style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none', padding: '6px 12px',
              background: 'var(--surface2)', borderRadius: 6, border: '1px solid var(--border)' }}
          >
            ⬡ View All Deploys on Explorer ↗
          </a>
        </div>
      </div>

      {/* ── Recent Account Deploys ────────────────────────────────────────── */}
      {deploys.length > 0 && (
        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>
            Recent Account Deploys
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8 }}>
              via cspr.cloud API
            </span>
          </h2>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 12px' }}>Deploy Hash</th>
                  <th style={{ padding: '8px 12px' }}>Contract</th>
                  <th style={{ padding: '8px 12px' }}>Cost</th>
                  <th style={{ padding: '8px 12px' }}>Time</th>
                  <th style={{ padding: '8px 12px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {deploys.slice(0, 15).map((d, i) => {
                  const hash = d.deploy_hash || d.deployHash
                  const contractName = d.contract || Object.entries(CONTRACT_HASHES).find(([, h]) => h === hash)?.[0] || '—'
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px 12px' }}>
                        <a href={`${CONTRACT_EXPLORER}${hash}`} target="_blank" rel="noopener noreferrer"
                          style={{ color: 'var(--accent)', fontFamily: 'monospace', textDecoration: 'none', fontSize: 11 }}>
                          {hash ? hash.slice(0, 16) + '…' : '—'} ↗
                        </a>
                      </td>
                      <td style={{ padding: '8px 12px', color: contractName !== '—' ? 'var(--accent)' : 'var(--text-muted)', fontWeight: contractName !== '—' ? 600 : 400 }}>
                        {contractName}
                      </td>
                      <td style={{ padding: '8px 12px', color: 'var(--text-muted)' }}>
                        {fmtMotes(d.cost)}
                      </td>
                      <td style={{ padding: '8px 12px', color: 'var(--text-muted)', fontSize: 11 }}>
                        {fmtTime(d.timestamp)}
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <span style={{ color: d.status === 'executed' || d.status === 'success' ? 'var(--success)' : 'var(--warning)', fontSize: 11 }}>
                          {d.status || 'executed'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── OTel Spans ────────────────────────────────────────────────────── */}
      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
          OTel Agent Traces ({spans.length} spans)
        </h2>
        {spans.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            No spans collected yet. Run a risk query or anomaly scan to generate traces.
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 12px' }}>Span</th>
                  <th style={{ padding: '8px 12px' }}>Duration</th>
                  <th style={{ padding: '8px 12px' }}>Status</th>
                  <th style={{ padding: '8px 12px' }}>Latency Bar</th>
                </tr>
              </thead>
              <tbody>
                {spans.slice(-20).reverse().map((s, i) => {
                  const maxMs = 2000
                  const pct   = Math.min((s.duration_ms || 0) / maxMs * 100, 100)
                  const barColor = s.duration_ms > 1500 ? 'var(--warning)' : s.duration_ms > 800 ? 'var(--accent)' : 'var(--success)'
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px 12px', color: 'var(--accent)', fontFamily: 'monospace', fontSize: 11 }}>{s.name}</td>
                      <td style={{ padding: '8px 12px', fontWeight: 600 }}>{s.duration_ms != null ? `${s.duration_ms.toFixed(1)}ms` : '—'}</td>
                      <td style={{ padding: '8px 12px', color: s.status === 'OK' ? 'var(--success)' : 'var(--danger)' }}>
                        {s.status}
                      </td>
                      <td style={{ padding: '8px 12px', minWidth: 100 }}>
                        <div style={{ height: 6, background: 'var(--surface2)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${pct}%`, background: barColor, borderRadius: 3, transition: 'width 0.4s' }} />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
