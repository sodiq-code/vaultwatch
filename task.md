# VaultWatch Deployment Task

## Status: ACTIVE — June 22, 2026

## Objective
Get VaultWatch on-chain (Casper Testnet) before June 30 deadline.
Minimum: 1 transaction hash on testnet for hackathon eligibility.

## Keypair (GENERATED)
- Private: 199f8420c8df39e16d0b12d5afdcc34f2e61f6604e2d1aeaef8883d55cd71d55
- Public: e35b10cce65eb92e30ec83ea23d7654482509b0cc3313bcbe54a207a407499a2
- Faucet format: 01e35b10cce65eb92e30ec83ea23d7654482509b0cc3313bcbe54a207a407499a2
- Account hash: account-hash-dfe3488c7283d3944a399c7836bf6f482b969399cadccb75e8e126dcc74f3602

## Testnet Status
- Testnet is LIVE: block 8,268,303+, node 2.2.1
- DNS for rpc.testnet.casperlabs.io does NOT resolve from sandbox
- cspr.cloud testnet RPC: https://node.testnet.cspr.cloud/rpc (needs API key)
- tatum.io testnet RPC: https://casper-testnet.gateway.tatum.io (needs free API key)

## Faucet Status
- testnet.cspr.live/tools/faucet: WORKS but requires wallet sign-in (browser only)
- direct API: No unauthenticated faucet endpoint found
- validationcloud.io: No Casper listed
- Strategy: Use python casper-sdk + cspr.cloud or tatum to submit deploy

## Pending Steps (priority order)
1. [BLOCKING] Get RPC access → sign up for Tatum free account (email signup)
2. [BLOCKING] Fund account → can use tatum RPC to submit a self-fund via SDK
   OR: Use cspr.click skill from Casper AI Toolkit
3. Install Odra/cargo toolchain OR use Python casper SDK to deploy
4. Deploy contracts → get 8 TX hashes
5. Update README with TX hashes
6. Push to GitHub
7. Demo video

## Key Resources
- Casper AI Toolkit: https://www.casper.network/ai
- CSPR.click AI Agent Skill: installable coding skill
- Odra docs: https://docs.odra.dev
- Tatum dashboard: https://dashboard.tatum.io
- cspr.build signup: https://cspr.build (has account portal somewhere)
- RPC alternatives: NOWNodes (form at dorahacks discussion)

## Notes
- Hackathon requires: working prototype + transaction on testnet + demo video + GitHub
- The faucet sends 5000 CSPR to the account - once funded all deploys work
- casper-python-sdk is available on PyPI: pip install casper-sdk
- Casper uses WASM deploys (not EVM), so toolchain matters
