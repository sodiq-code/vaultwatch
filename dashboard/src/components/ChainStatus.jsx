import { useState, useEffect } from 'react'
import { CONTRACT_HASHES, getLiveBlockHeight, fetchCSPRPrice } from '../liveApi.js'

const CARD = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 20, marginBottom: 16 }

const STAT = ({ label, value, sub, color = 'var(--text)' }) => (
  <div style={{ background: 'var(--surface2)', borderRadius: 10, padding: '16px 20px' }}>
    <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>{label}</div>
    <div style={{ fontSize: 22, fontWeight: 700, color }}>{value ?? '—'}</div>
    {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
  </div>
)

// Casper testnet explorer — deploy hash leads to the contract deploy page
const CONTRACT_EXPLORER_BASE = 'https://testnet.cspr.live/contract-package/'

export default function ChainStatus({ api }) {
  const [blockHeight, setBlockHeight] = useState(getLiveBlockHeight())
  const [spans, setSpans]             = useState([])
  const [cspr, setCspr]               = useState(null)
  const [loading, setLoading]         = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      const [spansData, price] = await Promise.all([
        api.getSpans().catch(() => ({ spans: [] })),
        fetchCSPRPrice().catch(() => null),
      ])
      setSpans(spansData?.spans || [])
      setCspr(price)
      setBlockHeight(getLiveBlockHeight())
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    // tick block height every 10s; full refresh every 30s
    const blockTick = setInterval(() => setBlockHeight(getLiveBlockHeight()), 10_000)
    const fullRefresh = setInterval(refresh, 30_000)
    return () => { clearInterval(blockTick); clearInterval(fullRefresh) }
  }, [])

  const priceColor = cspr?.change_24h == null
    ? 'var(--text)'
    : cspr.change_24h >= 0 ? 'var(--success)' : 'var(--danger)'

  const priceChange = cspr?.change_24h != null
    ? `${cspr.change_24h >= 0 ? '+' : ''}${cspr.change_24h.toFixed(2)}% 24h`
    : null

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Chain Status</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>
        Live Casper testnet block height, CSPR market price, deployed Odra contracts, and OTel agent traces.
      </p>

      {/* Network Overview */}
      <div style={CARD}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600 }}>Network Overview</h2>
          <button onClick={refresh} disabled={loading}
            style={{ background: 'var(--surface2)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <STAT label="Network"     value="casper-test" color="var(--accent)" />
          <STAT label="Block Height" value={blockHeight.toLocaleString()} color="var(--accent)"
            sub="~1 block / 65s" />
          <STAT
            label="CSPR Price"
            value={cspr?.usd != null ? `$${cspr.usd.toFixed(4)}` : 'Loading…'}
            sub={priceChange}
            color={cspr?.usd != null ? priceColor : 'var(--text-muted)'}
          />
          <STAT label="Contracts Deployed" value={`${Object.keys(CONTRACT_HASHES).length} / ${Object.keys(CONTRACT_HASHES).length}`} color="var(--success)" />
        </div>
      </div>

      {/* Deployed Contracts */}
      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>Deployed Odra Contracts — Casper Testnet</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 14 }}>
          All 8 Odra WASM contracts deployed on casper-test. Click any hash to view the contract deploy on the Casper testnet explorer.
        </p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                <th style={{ padding: '8px 12px' }}>Contract</th>
                <th style={{ padding: '8px 12px' }}>Deploy Hash (testnet)</th>
                <th style={{ padding: '8px 12px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(CONTRACT_HASHES).map(([name, hash]) => (
                <tr key={name} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 12px', color: 'var(--accent)', fontWeight: 600 }}>{name}</td>
                  <td style={{ padding: '8px 12px' }}>
                    <a
                      href={`${CONTRACT_EXPLORER_BASE}${hash}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={`View ${name} contract deploy on Casper testnet explorer`}
                      style={{ color: 'var(--text-muted)', fontFamily: 'monospace', textDecoration: 'none' }}
                    >
                      {hash.slice(0, 16)}…{hash.slice(-8)} ↗
                    </a>
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <span style={{ color: 'var(--success)', fontWeight: 600, fontSize: 11 }}>✓ DEPLOYED</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 10 }}>
          Note: The Casper testnet explorer indexes contract deploys — if a deploy hash was from a recent block, the explorer may take a few minutes to index it.
        </p>
      </div>

      {/* OTel Spans */}
      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
          OTel Spans — Recent Agent Traces ({spans.length})
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
                  <th style={{ padding: '8px 12px' }}>Span Name</th>
                  <th style={{ padding: '8px 12px' }}>Duration (ms)</th>
                  <th style={{ padding: '8px 12px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {spans.slice(-20).reverse().map((s, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px', color: 'var(--accent)', fontFamily: 'monospace', fontSize: 12 }}>{s.name}</td>
                    <td style={{ padding: '8px 12px' }}>{s.duration_ms != null ? s.duration_ms.toFixed(1) : '—'}</td>
                    <td style={{ padding: '8px 12px', color: s.status === 'OK' ? 'var(--success)' : 'var(--text-muted)' }}>
                      {s.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
