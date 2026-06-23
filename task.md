# VaultWatch Fix Plan
## Goal: Fix all 5 gaps (skip demo video)

### Priority Order
1. Fix casper_client.py deploy (unblocks everything)
2. pip install pytest-asyncio + run tests
3. Fix SDK name (casper-sentinel) + publish to PyPI
4. Create vaultwatch_mcp/package.json + publish to npm
5. Deploy all 8 contracts to testnet
6. Update dashboard with real hashes + redeploy Vercel

### Key Facts
- pycspr 1.2.0: create_deploy_parameters(account, chain_name, dependencies, gas_price, timestamp, ttl)
- Payment goes into create_deploy(params, payment, session) as DeployOfModuleBytes
- SDK setup.py name must change to "casper-sentinel"
- Sidecar path: ./streaming/sidecar_client.py (not sentinel/)
- Total real tests: 101

### Status
- [ ] casper_client.py fixed
- [ ] pytest-asyncio installed + tests passing
- [ ] SDK renamed + published
- [ ] MCP npm package created + published
- [ ] Contracts deployed (real hashes)
- [ ] Dashboard updated + Vercel redeployed
