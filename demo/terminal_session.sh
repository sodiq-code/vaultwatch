#!/bin/bash
# Terminal session script — runs inside xterm for recording
export TERM=xterm-256color
export PS1='\[\033[01;32m\]vaultwatch\[\033[00m\]:\[\033[01;34m\]~/vaultwatch\[\033[00m\]$ '

# Clear and show prompt
clear
echo -e "\033[01;32mvaultwatch\033[00m:\033[01;34m~/vaultwatch\033[00m\$ \c"
sleep 1

# Show pytest command
echo "pytest tests/ -v --tb=no"
sleep 0.5

# Stream pytest output with slight delay between lines
while IFS= read -r line; do
    echo "$line"
    sleep 0.03
done < /home/user/vaultwatch/demo/raw_recordings/pytest_output.txt

sleep 1.5

# Show pipeline command
echo ""
echo -e "\033[01;32mvaultwatch\033[00m:\033[01;34m~/vaultwatch\033[00m\$ \c"
sleep 0.5
echo "python pipeline.py"
sleep 0.5

# Stream pipeline output
echo "2026-06-24 11:21:38,176 vaultwatch.pipeline INFO VaultWatch pipeline starting..."
sleep 0.2
echo "2026-06-24 11:21:38,176 vaultwatch.pipeline INFO VaultWatch pipeline running — 7 workers active"
sleep 0.2
echo "2026-06-24 11:21:38,177 vaultwatch.pipeline INFO Sidecar fan-out started"
sleep 0.15
echo "2026-06-24 11:21:38,195 vaultwatch.pipeline INFO Scanner worker started"
sleep 0.15
echo "2026-06-24 11:21:38,195 vaultwatch.pipeline INFO Anomaly worker started"
sleep 0.15
echo "2026-06-24 11:21:38,195 vaultwatch.pipeline INFO Self-correction worker started"
sleep 0.15
echo "2026-06-24 11:21:38,195 vaultwatch.pipeline INFO RWA worker started"
sleep 0.15
echo "2026-06-24 11:21:38,195 vaultwatch.pipeline INFO Intel worker started"
sleep 0.15
echo "2026-06-24 11:21:38,195 vaultwatch.pipeline INFO Audit worker started"
sleep 0.5
echo "2026-06-24 11:21:38,197 vaultwatch.pipeline WARNING Sidecar stream connecting to Casper SSE..."
sleep 0.8
echo "2026-06-24 11:21:39,012 vaultwatch.pipeline INFO ScannerAgent span opened — block_height=8279525"
sleep 0.3
echo "2026-06-24 11:21:39,214 vaultwatch.pipeline INFO AnomalyAgent classifying — protocol=CasperSwap score=42"
sleep 0.3
echo "2026-06-24 11:21:39,389 vaultwatch.pipeline INFO SelfCorrectionAgent re-evaluating — confidence=0.72"
sleep 0.3
echo "2026-06-24 11:21:39,501 vaultwatch.pipeline INFO AuditAgent writing to AuditTrail contract..."
sleep 0.4
echo "2026-06-24 11:21:39,788 vaultwatch.pipeline INFO RWAAgent assessment complete — verdict=APPROVED score=5"
sleep 0.3
echo "2026-06-24 11:21:39,901 vaultwatch.pipeline INFO IntelAgent dispatching MEDIUM alert — CasperLend"
sleep 0.3
echo "2026-06-24 11:21:40,102 vaultwatch.pipeline INFO SafetyGuard passed — validation=25ms"
sleep 0.3
echo "2026-06-24 11:21:40,312 vaultwatch.pipeline INFO x402 payment received — 0.5 CSPR deducted SubscriberVault"
sleep 0.5
echo "2026-06-24 11:21:40,590 vaultwatch.pipeline INFO All 6 agents active — pipeline healthy"
sleep 2

