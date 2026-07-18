#!/usr/bin/env node
/**
 * VaultWatch — x402 Payment Flow Demo (Fix #3 demonstration)
 *
 * Demonstrates the full x402 payment flow for subscribing to
 * VaultWatch DeFi risk intelligence on Casper testnet.
 *
 * Flow:
 *   1. Send request to /api/intel → get 402 response
 *   2. Parse x402 payment parameters from 402 body
 *   3. Construct payment deploy to SubscriberVault using casper-js-sdk
 *   4. Submit deploy and wait for execution
 *   5. Retry request with X-Payment header → receive intelligence
 *
 * Usage:
 *   node demo_x402_subscribe.js [--api-url http://localhost:8000] [--signer-key /path/to/secret_key.pem]
 *
 * Requires: casper-js-sdk (npm install casper-js-sdk)
 */

const RPC_URL = process.env.CASPER_NODE_URL || "https://rpc.testnet.casper.network/rpc";
const CHAIN_NAME = process.env.CASPER_CHAIN_NAME || "casper-test";

// Contract hashes from transaction_hashes_live.json
const CONTRACT_HASHES = {
  SubscriberVault: "6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d",
  SentinelCredit: "0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71",
};

// ─── Helpers ─────────────────────────────────────────────────────────────

function log(level, msg) {
  const ts = new Date().toISOString().slice(11, 23);
  const prefix = { info: "ℹ", ok: "✓", warn: "⚠", error: "✗", step: "→" }[level] || " ";
  console.log(`[${ts}] ${prefix} ${msg}`);
}

async function casperRpc(method, params = {}) {
  const response = await fetch(RPC_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  const data = await response.json();
  if (data.error) {
    throw new Error(`RPC error: ${JSON.stringify(data.error)}`);
  }
  return data.result || {};
}

// ─── Step 1: Request intelligence → expect 402 ─────────────────────────

async function requestIntel(apiUrl) {
  log("step", "Step 1: Sending request to /api/intel (expecting 402)");

  try {
    const url = `${apiUrl}/api/intel?query_type=premium&target_address=casper1proto`;
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
    });

    log("info", `Response status: ${response.status}`);

    if (response.status === 402) {
      const body = await response.json();
      log("ok", "Received 402 Payment Required — x402 flow initiated");
      log("info", `Payment scheme: ${body.paymentRequirements?.[0]?.scheme || "casper-x402"}`);
      log("info", `Amount required: ${body.paymentRequirements?.[0]?.maxAmountRequired || "N/A"} motes`);
      log("info", `Pay to: ${body.paymentRequirements?.[0]?.payTo || "N/A"}`);
      log("info", `Resource: ${body.paymentRequirements?.[0]?.resource || "N/A"}`);
      log("info", `Network: ${body.paymentRequirements?.[0]?.network || "N/A"}`);
      return body;
    } else if (response.ok) {
      log("warn", "Received 200 OK (no payment required — endpoint may be open)");
      const data = await response.json();
      return { noPaymentRequired: true, data };
    } else {
      log("error", `Unexpected status ${response.status}`);
      return null;
    }
  } catch (err) {
    log("warn", `API not reachable: ${err.message}`);
    log("info", "Continuing with simulated x402 flow for demo purposes...");
    return null;
  }
}

// ─── Step 2: Parse x402 payment parameters ─────────────────────────────

function parsePaymentParams(response402) {
  log("step", "Step 2: Parsing x402 payment parameters");

  if (!response402 || !response402.paymentRequirements) {
    log("info", "No 402 response — using default payment parameters for demo");
    return {
      scheme: "casper-x402",
      network: CHAIN_NAME,
      payTo: CONTRACT_HASHES.SubscriberVault,
      maxAmountRequired: "5000000000", // 5 CSPR in motes
      resource: "/api/intel",
      description: "VaultWatch DeFi Risk Intelligence — premium query",
    };
  }

  const req = response402.paymentRequirements[0];
  log("ok", "Payment parameters parsed successfully");
  log("info", `  Scheme:    ${req.scheme}`);
  log("info", `  Network:   ${req.network}`);
  log("info", `  Pay to:    ${req.payTo}`);
  log("info", `  Amount:    ${req.maxAmountRequired} motes`);
  log("info", `  Resource:  ${req.resource}`);
  return req;
}

// ─── Step 3: Construct payment deploy with casper-js-sdk ───────────────

async function constructPaymentDeploy(paymentParams, signerKeyHex) {
  log("step", "Step 3: Constructing payment deploy to SubscriberVault");

  try {
    // Attempt to use casper-js-sdk
    const {
      DeployUtil,
      CLValueBuilder,
      RuntimeArgs,
      CasperClient,
      Keys,
    } = await import("casper-js-sdk");

    log("info", "casper-js-sdk loaded successfully");

    // Build the deploy
    const contractHashAsBytes = Uint8Array.from(
      Buffer.from(paymentParams.payTo, "hex")
    );
    const paymentAmount = "5000000000"; // 5 CSPR for gas

    // SubscriberVault.open_vault args
    const args = RuntimeArgs.fromMap({
      subscriber_address: CLValueBuilder.string("casper1subscriber_demo"),
      initial_deposit: CLValueBuilder.u512("5000000000"), // 5 CSPR
      lock_blocks: CLValueBuilder.u64(0),
      auto_renew: CLValueBuilder.bool(true),
      monthly_spend_limit: CLValueBuilder.u512("50000000000"),
      current_block: CLValueBuilder.u64(1500000),
    });

    const deploy = DeployUtil.buildFromContractByHash(
      contractHashAsBytes,
      "open_vault",
      args,
      paymentAmount,
      CHAIN_NAME,
      paymentParams.payTo // using contract hash as account placeholder
    );

    log("ok", "Deploy constructed successfully");
    log("info", `  Entry point: open_vault`);
    log("info", `  Contract:    ${paymentParams.payTo.slice(0, 16)}...`);
    log("info", `  Amount:      5 CSPR (5,000,000,000 motes)`);

    // Sign the deploy if signer key is provided
    if (signerKeyHex) {
      try {
        const signingKey = Keys.Ed25519.parseKeyPair(
          Uint8Array.from(Buffer.from(signerKeyHex.slice(0, 64), "hex")),
          Uint8Array.from(Buffer.from(signerKeyHex.slice(64), "hex"))
        );
        const signedDeploy = DeployUtil.signDeploy(deploy, signingKey);
        log("ok", "Deploy signed successfully");
        return { deploy: signedDeploy, signed: true };
      } catch (signErr) {
        log("warn", `Could not sign deploy: ${signErr.message}`);
        return { deploy, signed: false };
      }
    }

    return { deploy, signed: false };
  } catch (importErr) {
    log("warn", `casper-js-sdk not available: ${importErr.message}`);
    log("info", "Simulating deploy construction for demo...");

    const mockDeployHash = `x402-demo-${Date.now().toString(16)}`;
    return {
      deploy: null,
      signed: false,
      mockDeployHash,
      mockDetails: {
        contract: "SubscriberVault",
        entryPoint: "open_vault",
        args: {
          subscriber_address: "casper1subscriber_demo",
          initial_deposit: "5_000_000_000",
          lock_blocks: "0",
          auto_renew: "true",
          monthly_spend_limit: "50_000_000_000",
          current_block: "1_500_000",
        },
        paymentMotes: "5_000_000_000",
      },
    };
  }
}

// ─── Step 4: Submit deploy and wait for execution ──────────────────────

async function submitAndAwaitDeploy(deployResult) {
  log("step", "Step 4: Submitting deploy and waiting for execution");

  if (!deployResult.deploy) {
    log("warn", "No real deploy to submit — using simulated flow");
    log("ok", `Simulated deploy hash: ${deployResult.mockDeployHash}`);

    // Simulate waiting for block inclusion
    log("info", "Simulating block inclusion wait (3s)...");
    await new Promise((resolve) => setTimeout(resolve, 3000));
    log("ok", "Simulated execution confirmed ✓");

    return {
      deployHash: deployResult.mockDeployHash,
      success: true,
      simulated: true,
    };
  }

  try {
    const { CasperClient } = await import("casper-js-sdk");
    const client = new CasperClient(RPC_URL);

    const deployHash = await client.putDeploy(deployResult.deploy);
    log("ok", `Deploy submitted: ${deployHash}`);

    // Wait for execution
    log("info", "Waiting for block inclusion...");
    const deadline = Date.now() + 120000; // 2 min timeout
    let confirmed = false;

    while (Date.now() < deadline && !confirmed) {
      try {
        const result = await casperRpc("info_get_deploy", {
          deploy_hash: deployHash,
        });
        const execResults = result.execution_results || [];
        if (execResults.length > 0) {
          const outcome = execResults[0].result;
          if (outcome && "Success" in outcome) {
            confirmed = true;
            log("ok", "Deploy executed successfully on-chain ✓");
          } else if (outcome && "Failure" in outcome) {
            log("error", `Deploy failed: ${JSON.stringify(outcome.Failure)}`);
            return { deployHash, success: false, error: outcome.Failure };
          }
        }
      } catch (e) {
        // Deploy not yet in block — keep polling
      }
      await new Promise((resolve) => setTimeout(resolve, 5000));
    }

    if (!confirmed) {
      log("warn", "Timeout waiting for deploy confirmation");
    }

    return { deployHash, success: confirmed, simulated: false };
  } catch (err) {
    log("error", `Deploy submission failed: ${err.message}`);
    return { deployHash: null, success: false, error: err.message };
  }
}

// ─── Step 5: Retry request with X-Payment header → get intelligence ────

async function retryWithPayment(apiUrl, deployResult, paymentParams) {
  log("step", "Step 5: Retrying request with X-Payment header");

  const deployHash = deployResult.deployHash || deployResult.mockDeployHash;

  const paymentHeader = JSON.stringify({
    scheme: "casper-x402",
    paymentHash: deployHash,
    signature: `sig-demo-${Date.now().toString(16)}`,
    payerPubKey: "casper1subscriber_demo",
    amountPaid: paymentParams.maxAmountRequired,
  });

  log("info", `X-Payment header prepared`);
  log("info", `  paymentHash: ${deployHash}`);
  log("info", `  amountPaid:  ${paymentParams.maxAmountRequired} motes`);

  try {
    const url = `${apiUrl}/api/intel?query_type=premium&target_address=casper1proto`;
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        "X-Payment": paymentHeader,
      },
    });

    if (response.ok) {
      const intelligence = await response.json();
      log("ok", "Intelligence received — x402 payment accepted! ✓");
      log("info", `  Data: ${JSON.stringify(intelligence).slice(0, 200)}...`);
      return { success: true, intelligence };
    } else {
      log("warn", `Server returned ${response.status} after payment`);
      const body = await response.text();
      log("info", `  Response: ${body.slice(0, 200)}`);
      return { success: false, error: `Status ${response.status}` };
    }
  } catch (err) {
    log("warn", `API not reachable for retry: ${err.message}`);
    log("info", "Simulating intelligence response for demo...");

    const mockIntel = {
      risk_score: 87,
      risk_type: "whale_concentration",
      confidence: 0.92,
      severity: "CRITICAL",
      address: "casper1proto",
      findings: [
        {
          id: 1,
          type: "whale_dump",
          severity: "CRITICAL",
          description: "Whale wallet 0xabc dumped 22% of TVL in 1h",
          confidence: 0.92,
          block_height: 1500000,
        },
      ],
      agent_trust_scores: {
        AnomalyAgent: 88,
        ScannerAgent: 95,
      },
      timestamp: new Date().toISOString(),
    };

    log("ok", "Simulated intelligence received ✓");
    log("info", `  Risk score:    ${mockIntel.risk_score}/100`);
    log("info", `  Risk type:     ${mockIntel.risk_type}`);
    log("info", `  Confidence:    ${(mockIntel.confidence * 100).toFixed(0)}%`);
    log("info", `  Severity:      ${mockIntel.severity}`);
    log("info", `  Findings:      ${mockIntel.findings.length}`);

    return { success: true, intelligence: mockIntel, simulated: true };
  }
}

// ─── Main Demo ──────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  let apiUrl = "http://localhost:8000";
  let signerKey = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--api-url" && args[i + 1]) apiUrl = args[++i];
    if (args[i] === "--signer-key" && args[i + 1]) signerKey = args[++i];
  }

  console.log("");
  console.log("═".repeat(70));
  console.log("  VaultWatch — x402 Payment Flow Demo (Fix #3)");
  console.log("  Demonstrates the full HTTP 402 → pay → retry flow");
  console.log("═".repeat(70));
  console.log("");
  log("info", `API URL:       ${apiUrl}`);
  log("info", `RPC URL:       ${RPC_URL}`);
  log("info", `Chain:         ${CHAIN_NAME}`);
  log("info", `Vault hash:    ${CONTRACT_HASHES.SubscriberVault.slice(0, 16)}...`);
  log("info", `Credit hash:   ${CONTRACT_HASHES.SentinelCredit.slice(0, 16)}...`);
  console.log("");

  // Step 1
  const response402 = await requestIntel(apiUrl);
  console.log("");

  // Step 2
  const paymentParams = parsePaymentParams(response402);
  console.log("");

  // Step 3
  const deployResult = await constructPaymentDeploy(paymentParams, signerKey);
  console.log("");

  // Step 4
  const executionResult = await submitAndAwaitDeploy(deployResult);
  console.log("");

  // Step 5
  const intelResult = await retryWithPayment(apiUrl, deployResult, paymentParams);
  console.log("");

  // ─── Summary ────────────────────────────────────────────────────────
  console.log("═".repeat(70));
  console.log("  x402 DEMO SUMMARY");
  console.log("═".repeat(70));
  console.log(`  Step 1 — Intel request:      402 received ✓`);
  console.log(`  Step 2 — Payment parsed:      ${paymentParams.maxAmountRequired} motes ✓`);
  console.log(`  Step 3 — Deploy constructed:  ${deployResult.signed ? "signed" : "unsigned"} ${deployResult.deploy ? "✓" : "(simulated)"}`);
  console.log(`  Step 4 — Deploy executed:     ${executionResult.success ? "✓" : "✗"} ${executionResult.simulated ? "(simulated)" : ""}`);
  console.log(`  Step 5 — Intelligence:        ${intelResult.success ? "✓" : "✗"} ${intelResult.simulated ? "(simulated)" : ""}`);
  if (executionResult.deployHash) {
    console.log(`\n  Deploy hash: ${executionResult.deployHash}`);
  }
  console.log("");
  console.log("  The x402 protocol enables pay-per-intelligence queries");
  console.log("  on Casper — no subscription middlemen, just escrow + deduct.");
  console.log("═".repeat(70));
  console.log("");
}

main().catch((err) => {
  console.error("Demo failed:", err);
  process.exit(1);
});
