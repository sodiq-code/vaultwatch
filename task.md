# VaultWatch Fix Session — 2026-06-24

## Situation
- Repo: https://github.com/sodiq-code/vaultwatch
- Deadline: June 30, 2026

## 3 Gaps to Close

### 1. Tests — pytest.ini missing (asyncio mode config)
- Status: Tests already PASS (107 passed) locally
- pytest-asyncio mode is STRICT by default in new version
- Need: add pytest.ini with asyncio_mode=auto so CI runs cleanly
- Also: add conftest.py to set asyncio_mode

### 2. Contract deployment — new funded account
- Old account: 0202c223a43185563f... (0 CSPR, all deploys FAILED)
- New account public key: 0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116
- User says this new account has funds
- NOTE: The hex provided (0202c27a...) is the PUBLIC KEY (compressed secp256k1, 33 bytes = 66 hex + 02 prefix = starts with 0202)
- We need the SECRET KEY PEM to deploy — user gave public key, not private key
- Strategy: Update liveApi.js DEPLOYER_ACCOUNT to new public key
- For actual deployment — the deploy_live.py needs secret_key.pem
- Current deploy_hashes.json has mock hashes (sha256 generated)
- Current dashboard liveApi.js has fake hashes hardcoded
- deploy_hashes_live.json has all FAILED (insufficient balance)
- We need to try deploying with new account OR keep existing hashes and update DEPLOYER_ACCOUNT

### 3. Vercel deploy + GitHub push
- GitHub token: [stored in env, not committed]
- Vercel token: [stored in env, not committed]
- Need to push all changes and deploy dashboard to Vercel

## Action Plan

1. Add pytest.ini with asyncio_mode=auto
2. Update DEPLOYER_ACCOUNT in liveApi.js to new public key
3. Try to deploy contracts with new account if we can derive key
4. Push all to GitHub
5. Deploy dashboard to Vercel

## Notes
- The key 0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116
  appears to be a compressed secp256k1 public key (02 prefix, 33 bytes)
- We cannot deploy without the PRIVATE key PEM
- But we CAN update the DEPLOYER_ACCOUNT so the dashboard queries the right account
- The existing CONTRACT_HASHES in liveApi.js may be from a previous attempt (broadcast_deploys.py output)
