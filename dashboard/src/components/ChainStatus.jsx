/**
 * ChainStatus — Enhanced chain status with CSPR charts, network info,
 * deploy list, and latency spans.
 */
import { useState, useEffect } from 'react'
import { GlassCard } from '../ui/GlassCard.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { Badge, SourceBadge, HexBadge } from '../ui/Badge.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { SkeletonBlock } from '../ui/Skeleton.jsx'
import { CSPRPriceChart } from '../charts/CSPRPriceChart.jsx'
import { LatencyChart } from '../charts/LatencyChart.jsx'
import { CONTRACT_HASHES } from '../liveApi.js'

export function ChainStatus({ api, addToast }) {
  const [price, setPrice] = useState(null)
  const [priceHistory, setPriceHistory] = useState([])
  const [network, setNetwork] = useState(null)
  const [deploys, setDeploys] = useState([])
  const [spans, setSpans] = useState([])
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sources, setSources] = useState({})

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 15000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    const newSources = {}
    try {
      const priceData = await api.fetchCSPRPrice()
      if (priceData) {
        setPrice(priceData)
        newSources.price = priceData._source || 'live'
      }
    } catch {}
    try {
      const historyData = await api.fetchCSPRPriceHistory()
      if (historyData) {
        setPriceHistory(historyData)
        newSources.history = historyData._source || 'live'
      }
    } catch {}
    try {
      const netData = await api.fetchNetworkInfo()
      if (netData) {
        setNetwork(netData)
        newSources.network = netData._source || 'live'
      }
    } catch {}
    try {
      const deployData = await api.fetchAccountDeploys(10)
      if (deployData) {
        setDeploys(Array.isArray(deployData) ? deployData : [])
        newSources.deploys = deployData._source || 'live'
      }
    } catch {}
    try {
      const spansData = await api.getSpans()
      if (spansData?.spans) {
        const mapped = spansData.spans.map(s => ({
          name: s.name,
          spanId: s.trace_id || s.spanId,
          durationMs: s.duration_ms || s.durationMs || 0,
          status: s.status || 'OK',
        }))
        setSpans(mapped)
        newSources.spans = spansData._source || 'live'
      }
    } catch {}
    try {
      const healthData = await api.health()
      if (healthData) {
        setHealth(healthData)
        newSources.health = healthData._source || 'live'
      }
    } catch {}
    setSources(newSources)
    setLoading(false)
  }

  if (loading) {
    return (
      <div style={{ padding: 'var(--space-lg)' }}>
        <SkeletonBlock height={40} style={{ marginBottom: 'var(--space-lg)' }} />
        <SkeletonBlock height={300} />
      </div>
    )
  }

  const blockHeight = network?.block_height || api.getBlockHeight()
  const csprUsd = price?.usd
  const change24h = price?.change_24h

  return (
    <div className="fade-in" style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="Chain Status"
        subtitle="Casper testnet network status, CSPR price, and contract deploys"
        icon="🔗"
        source={sources.network || 'fallback'}
        actions={
          <GradientBtn variant="ghost" size="sm" onClick={loadData} icon="⟳">
            Refresh
          </GradientBtn>
        }
      />

      {/* Stats row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 'var(--space-md)',
        marginBottom: 'var(--space-lg)',
      }}>
        <StatCard
          label="CSPR Price"
          value={csprUsd || 0}
          prefix="$"
          icon="💰"
          color={change24h > 0 ? 'var(--success)' : 'var(--danger)'}
          trend={change24h}
          trendLabel="24h"
          source={sources.price}
        />
        <StatCard label="Block Height" value={blockHeight || 0} icon="📦" color="var(--accent)" source={sources.network} />
        <StatCard label="Market Cap" value={price?.market_cap || 0} prefix="$" icon="📊" color="var(--accent2)" source={sources.price} />
        <StatCard label="Agents" value={health?.agents || 7} icon="🧠" color="var(--success)" source={sources.health} />
        <StatCard label="Contracts" value={Object.keys(CONTRACT_HASHES).length} icon="📋" color="var(--warning)" animated={false} />
        <StatCard label="Groq" value={health?.groq_connected ? 'Connected' : 'Fallback'} icon="🤖" color={health?.groq_connected ? 'var(--success)' : 'var(--warning)'} animated={false} />
      </div>

      {/* Two column: Price chart + Network info */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--space-lg)',
        marginBottom: 'var(--space-lg)',
      }}>
        {/* Price chart */}
        <GlassCard hover={false} style={{ padding: 'var(--space-md)' }}>
          <div style={{
            fontSize: 'var(--font-size-sm)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text-secondary)',
            marginBottom: 'var(--space-sm)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            CSPR/USD — 7 Day
            <SourceBadge source={sources.history} />
          </div>
          {priceHistory.length > 0 && <CSPRPriceChart data={priceHistory} height={180} />}
        </GlassCard>

        {/* Network info */}
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-sm)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text-secondary)',
            marginBottom: 'var(--space-md)',
          }}>
            Network Info
          </div>
          {network && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              {[
                { label: 'Block Height', value: network.block_height?.toLocaleString(), color: 'var(--accent)' },
                { label: 'Era ID', value: network.era_id, color: 'var(--accent2)' },
                { label: 'Validator', value: network.validator, color: 'var(--text-secondary)', mono: true },
                { label: 'TX Count', value: network.tx_count, color: 'var(--warning)' },
                { label: 'Transfers', value: network.transfer_count, color: 'var(--success)' },
                { label: 'Timestamp', value: new Date(network.timestamp).toLocaleString(), color: 'var(--text-muted)' },
              ].map((item, i) => (
                <div key={i} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 'var(--font-size-sm)',
                  borderBottom: '1px solid var(--border)',
                  padding: '6px 0',
                }}>
                  <span style={{ color: 'var(--text-muted)' }}>{item.label}</span>
                  <span style={{ color: item.color, fontFamily: item.mono ? 'var(--font-mono)' : 'var(--font)' }}>{String(item.value)}</span>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>

      {/* Contract hashes */}
      <GlassCard hover={false} style={{ padding: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        <div style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-semibold)',
          color: 'var(--text)',
          marginBottom: 'var(--space-md)',
        }}>
          Deployed Contracts
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
          {Object.entries(CONTRACT_HASHES).map(([name, hash], i) => (
            <div key={name} className="glass-row-hover" style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              padding: 'var(--space-sm)',
              background: 'rgba(14, 18, 30, 0.4)',
              borderRadius: 'var(--radius-sm)',
            }}>
              <HexBadge label={i + 1} />
              <span style={{
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-semibold)',
                color: 'var(--accent)',
                flex: 1,
              }}>
                {name}
              </span>
              <span style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                wordBreak: 'break-all',
              }}>
                {hash.slice(0, 16)}…{hash.slice(-8)}
              </span>
              <a
                href={`https://testnet.cspr.live/deploy/${hash}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 'var(--font-size-xs)', color: 'var(--accent)' }}
              >
                View ↗
              </a>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Latency spans */}
      {spans.length > 0 && (
        <GlassCard hover={false} style={{ padding: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-sm)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text-secondary)',
            marginBottom: 'var(--space-sm)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            OTel Latency Spans
            <SourceBadge source={sources.spans} />
          </div>
          <LatencyChart spans={spans} height={180} />
        </GlassCard>
      )}

      {/* Recent deploys */}
      {deploys.length > 0 && (
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
            marginBottom: 'var(--space-md)',
          }}>
            Recent Deploys
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
            {deploys.slice(0, 10).map((deploy, i) => (
              <div key={deploy.deploy_hash || i} className="glass-row-hover" style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                padding: 'var(--space-sm)',
                background: 'rgba(14, 18, 30, 0.4)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--font-size-sm)',
              }}>
                <Badge size="xs" colorScheme={deploy.status === 'executed' || deploy.status === 'success' ? 'success' : 'danger'}>
                  {deploy.status}
                </Badge>
                <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {deploy.deploy_hash?.slice(0, 12)}…
                </span>
                <span style={{ color: 'var(--text-secondary)', flex: 1 }}>{deploy.contract || ''}</span>
                <span style={{ color: 'var(--text-dark)', fontSize: 'var(--font-size-xs)' }}>
                  {deploy.timestamp ? new Date(deploy.timestamp).toLocaleTimeString() : ''}
                </span>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  )
}

export default ChainStatus
