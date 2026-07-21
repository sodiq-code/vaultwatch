import React, { useState, useEffect, useCallback } from 'react';
import { fetchFindings, CONTRACT_EXPLORER_LINKS } from '../liveApi.js';

// FIX #18: Removed hardcoded LIVE_FINDINGS array — data comes from live API
const SEVERITY_COLORS = {
  CRITICAL: { bg: '#ff1744', text: '#fff', glow: '0 0 12px rgba(255,23,68,0.6)' },
  HIGH:     { bg: '#ff6d00', text: '#fff', glow: '0 0 12px rgba(255,109,0,0.5)' },
  MEDIUM:   { bg: '#ffd600', text: '#000', glow: '0 0 10px rgba(255,214,0,0.4)' },
  LOW:      { bg: '#00e676', text: '#000', glow: '0 0 8px rgba(0,230,118,0.3)' },
};

const RISK_TYPE_ICONS = {
  rug_pull:        '🪤',
  whale_dump:      '🐋',
  depeg:           '📉',
  wash_trade:      '🔄',
  collateral_drop: '📊',
  flash_loan:      '⚡',
  anomalous_flow:  '🌊',
};

export default function LiveFeed() {
  const [findings, setFindings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('ALL');
  const [lastUpdate, setLastUpdate] = useState(null);

  const loadFindings = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchFindings(filter === 'ALL' ? null : filter, 50);
      setFindings(data);
      setLastUpdate(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  // Load on mount and on filter change
  useEffect(() => {
    loadFindings();
  }, [loadFindings]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(loadFindings, 30_000);
    return () => clearInterval(interval);
  }, [loadFindings]);

  const filteredFindings = filter === 'ALL'
    ? findings
    : findings.filter(f => f.severity === filter);

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.titleRow}>
          <h2 style={styles.title}>🔴 Live Intelligence Feed</h2>
          {lastUpdate && (
            <span style={styles.lastUpdate}>
              Updated {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>
        <p style={styles.subtitle}>
          Live findings from{' '}
          <a href={CONTRACT_EXPLORER_LINKS.AuditTrail} target="_blank" rel="noreferrer" style={styles.link}>
            AuditTrail contract
          </a>
          {' '}on Casper testnet
        </p>
      </div>

      {/* Filter buttons */}
      <div style={styles.filters}>
        {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => (
          <button
            key={sev}
            id={`filter-${sev.toLowerCase()}`}
            onClick={() => setFilter(sev)}
            style={{
              ...styles.filterBtn,
              ...(filter === sev ? styles.filterBtnActive : {}),
              ...(sev !== 'ALL' ? { borderColor: SEVERITY_COLORS[sev]?.bg, color: filter === sev ? '#fff' : SEVERITY_COLORS[sev]?.bg } : {}),
            }}
          >
            {sev}
          </button>
        ))}
        <button
          id="refresh-findings"
          onClick={loadFindings}
          style={styles.refreshBtn}
          disabled={loading}
        >
          {loading ? '⏳' : '🔄'} Refresh
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div style={styles.errorBanner}>
          ⚠️ API error: {error}. Showing cached data.
        </div>
      )}

      {/* Loading state */}
      {loading && findings.length === 0 && (
        <div style={styles.loadingState}>
          <div style={styles.spinner} />
          <span>Loading live findings from chain...</span>
        </div>
      )}

      {/* Empty state */}
      {!loading && filteredFindings.length === 0 && (
        <div style={styles.emptyState}>
          <div style={{ fontSize: 48 }}>✅</div>
          <p>No {filter !== 'ALL' ? filter : ''} risk findings detected.</p>
          <p style={{ fontSize: 12, color: '#666' }}>Agents are continuously monitoring Casper for DeFi risk.</p>
        </div>
      )}

      {/* Findings list */}
      <div style={styles.feedList}>
        {filteredFindings.map((finding, idx) => {
          const sev = finding.severity || 'LOW';
          const colors = SEVERITY_COLORS[sev] || SEVERITY_COLORS.LOW;
          const icon = RISK_TYPE_ICONS[finding.risk_type] || '⚠️';

          return (
            <div
              key={finding.id ?? idx}
              id={`finding-${finding.id ?? idx}`}
              style={{
                ...styles.findingCard,
                borderLeft: `4px solid ${colors.bg}`,
                boxShadow: colors.glow,
              }}
            >
              {/* Severity badge */}
              <div style={styles.findingHeader}>
                <span
                  style={{
                    ...styles.severityBadge,
                    background: colors.bg,
                    color: colors.text,
                  }}
                >
                  {sev}
                </span>
                <span style={styles.riskType}>
                  {icon} {(finding.risk_type || 'unknown').replace(/_/g, ' ')}
                </span>
                <span style={styles.confidence}>
                  {Math.round((finding.confidence || 0) * 100)}% confidence
                </span>
              </div>

              {/* Address */}
              <div style={styles.addressRow}>
                <span style={styles.label}>Address:</span>
                <code style={styles.address}>
                  {(finding.address || 'unknown').slice(0, 20)}...
                </code>
                {finding.audit_trail_tx && (
                  <a
                    href={`https://testnet.cspr.live/deploy/${finding.audit_trail_tx}`}
                    target="_blank"
                    rel="noreferrer"
                    style={styles.explorerLink}
                  >
                    View on chain →
                  </a>
                )}
              </div>

              {/* Description */}
              {finding.description && (
                <p style={styles.description}>{finding.description}</p>
              )}

              {/* Metadata */}
              <div style={styles.meta}>
                <span>🤖 {finding.agent_model || 'VaultWatch'}</span>
                {finding.block_height && (
                  <span>📦 Block #{finding.block_height}</span>
                )}
                {finding.timestamp && (
                  <span>🕐 {new Date(finding.timestamp * 1000).toLocaleTimeString()}</span>
                )}
                {finding.rwa_enriched && (
                  <span style={{ color: '#7c4dff' }}>🏦 RWA Enriched</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Stats bar */}
      {findings.length > 0 && (
        <div style={styles.statsBar}>
          {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => {
            const count = findings.filter(f => f.severity === sev).length;
            return count > 0 ? (
              <span
                key={sev}
                style={{ color: SEVERITY_COLORS[sev].bg, fontWeight: 600 }}
              >
                {count} {sev}
              </span>
            ) : null;
          })}
          <span style={{ color: '#666' }}>Total: {findings.length} findings</span>
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    background: 'rgba(15, 15, 30, 0.95)',
    borderRadius: 16,
    padding: '24px',
    border: '1px solid rgba(255,255,255,0.08)',
    backdropFilter: 'blur(20px)',
  },
  header: { marginBottom: 20 },
  titleRow: { display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  title: { margin: 0, fontSize: 20, fontWeight: 700, color: '#fff' },
  lastUpdate: { fontSize: 12, color: '#888', marginLeft: 'auto' },
  subtitle: { margin: '4px 0 0', fontSize: 13, color: '#666' },
  link: { color: '#7c4dff', textDecoration: 'none' },
  filters: { display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 },
  filterBtn: {
    padding: '6px 14px',
    borderRadius: 20,
    border: '1px solid rgba(255,255,255,0.2)',
    background: 'transparent',
    color: '#aaa',
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 600,
    transition: 'all 0.2s',
  },
  filterBtnActive: {
    background: 'rgba(124,77,255,0.3)',
    borderColor: '#7c4dff',
    color: '#fff',
  },
  refreshBtn: {
    padding: '6px 14px',
    borderRadius: 20,
    border: '1px solid rgba(255,255,255,0.15)',
    background: 'rgba(255,255,255,0.05)',
    color: '#aaa',
    cursor: 'pointer',
    fontSize: 12,
    marginLeft: 'auto',
  },
  errorBanner: {
    background: 'rgba(255,23,68,0.15)',
    border: '1px solid rgba(255,23,68,0.4)',
    borderRadius: 8,
    padding: '10px 16px',
    color: '#ff6b6b',
    fontSize: 13,
    marginBottom: 16,
  },
  loadingState: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    color: '#666',
    padding: '40px 20px',
    justifyContent: 'center',
  },
  spinner: {
    width: 20,
    height: 20,
    border: '2px solid rgba(124,77,255,0.3)',
    borderTop: '2px solid #7c4dff',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  },
  emptyState: {
    textAlign: 'center',
    padding: '40px 20px',
    color: '#666',
  },
  feedList: { display: 'flex', flexDirection: 'column', gap: 12 },
  findingCard: {
    background: 'rgba(255,255,255,0.03)',
    borderRadius: 12,
    padding: '16px',
    border: '1px solid rgba(255,255,255,0.06)',
    transition: 'all 0.3s',
  },
  findingHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
    flexWrap: 'wrap',
  },
  severityBadge: {
    padding: '3px 10px',
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 0.5,
  },
  riskType: {
    color: '#ccc',
    fontSize: 13,
    fontWeight: 600,
    textTransform: 'capitalize',
  },
  confidence: { color: '#888', fontSize: 12, marginLeft: 'auto' },
  addressRow: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 },
  label: { color: '#666', fontSize: 12 },
  address: {
    background: 'rgba(124,77,255,0.1)',
    color: '#c4b5fd',
    padding: '2px 8px',
    borderRadius: 4,
    fontSize: 12,
    fontFamily: 'monospace',
  },
  explorerLink: { color: '#7c4dff', fontSize: 12, textDecoration: 'none', marginLeft: 'auto' },
  description: { color: '#aaa', fontSize: 13, margin: '8px 0', lineHeight: 1.5 },
  meta: {
    display: 'flex',
    gap: 12,
    flexWrap: 'wrap',
    fontSize: 11,
    color: '#666',
    marginTop: 8,
  },
  statsBar: {
    display: 'flex',
    gap: 16,
    marginTop: 20,
    paddingTop: 16,
    borderTop: '1px solid rgba(255,255,255,0.06)',
    fontSize: 13,
    alignItems: 'center',
    flexWrap: 'wrap',
  },
};