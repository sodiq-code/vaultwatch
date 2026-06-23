# VaultWatch Deployment Status
## Date: 2026-06-23

## CRITICAL FINDINGS

### Bulk Memory - SOLVED
- All 8 WASMs had 358 memory.copy/fill ops
- Fixed via: wasm2wat → replace with call $__vw_memcpy → wat2wasm
- Patched WASM deploys successfully (no wasm preprocessing error)

### User Error 64658 = ExecutionError::MissingArg (code 122, offset 64536+122=64658)
- Contract's "call" export tries to read "entry_point" named arg
- This arg is missing during plain deployment
- Root cause: Odra 2.8 may expect Casper 2.x installation to pass args differently

### Casper 2.x vs Casper 1.x Contract Model
- Casper 2.x uses "Addressable Entity" model (different from 1.x)
- Odra 2.8.1 is supposedly Casper 2.x compatible
- But MissingArg during deployment is suspicious

## OPTIONS TO RESOLVE MissingArg

### Option A: Add "entry_point" arg to deployment = "call" (install mode)
- Odra's "call" export dispatches based on "entry_point" arg
- On first deploy, it should call the constructor/init
- Need to find what arg name Odra uses for constructor call

### Option B: Use odra-cli or casper-node deployment with proper session args
```
casper-client put-deploy
  --session-path contract.wasm
  --session-arg "entry_point:string='init'"  # maybe?
```

### Option C: Check if our custom #[no_mangle] memcpy is clobbering Odra internals
- Our lib.rs now has memcpy/memmove/memset with #[no_mangle]
- This might conflict with odra-casper-wasm-env's internal functions
- Remove these and rely on WAT patching only

### Option D: Deploy via Odra's odra-cli tool
- Odra provides its own deployment tool that handles args correctly

## FILES
- Patched wasm: /tmp/patch_wasm.py (transforms WAT)
- Deploy script: /tmp/deploy_all.sh
- Auth proxy script: /tmp/auth_proxy2.py

## Hashes from failed (MissingArg) deploys (wasm-preprocessor error fixed but MissingArg):
- AuditTrail patched: 4fb506c4611bb65d789e63d8865a095edbaf2035d7da5c6b11281109ae3e028f

## NEXT STEPS (in order):
1. Try Option C first - remove our custom memcpy functions from lib.rs, rebuild, patch, redeploy
2. Try adding "entry_point:string='init'" session arg  
3. Try Option D - use odra-cli

## Time Remaining: ~20 hours to July 1 deadline
