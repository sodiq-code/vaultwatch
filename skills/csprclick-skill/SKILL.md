---
name: csprclick-sdk-integration
title: CSPR.click SDK Integration
description: Use when integrating the CSPR.click Web SDK into a Casper dApp: connecting a wallet, signing transactions, handling events, customizing UI (theme/network/account selectors), or using the CSPR.cloud API proxy.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
user-invocable: true
---

# CSPR.click Web SDK — AI Skills Reference

Public docs base: `https://docs.cspr.click`. Use documentation paths below relative to this base. When fetching a documentation page, append `.md` to the path and add `?displayAgentInstructions=false` as a query parameter to receive Markdown instead of HTML; for example, `/cspr.click-sdk/integration/signing-transactions` means `https://docs.cspr.click/cspr.click-sdk/integration/signing-transactions.md?displayAgentInstructions=false`.

## Public Documentation

Read only the pages needed for the current task.

- Downloading and initializing the SDK `/cspr.click-sdk/integration/download-and-initialize`
- React Context Provider `/cspr.click-sdk/integration/react-context-provider`
- Handling events `/cspr.click-sdk/integration/handling-events`
- Connecting a Wallet `/cspr.click-sdk/integration/connecting-a-wallet`
- Signing transactions `/cspr.click-sdk/integration/signing-transactions`
- Tracking your transactions in real time `/cspr.click-sdk/integration/processing-status-updates`
- Customizing the Account Dropdown menu `/cspr.click-sdk/integration/customizing-the-top-bar/account-dropdown-menu`
- Adding a Theme selector to the Top Bar `/cspr.click-sdk/integration/customizing-the-top-bar/theme-selector`
- Adding a Network selector to the Top Bar `/cspr.click-sdk/integration/customizing-the-top-bar/network-selector`
- Displaying Account Identicons next to public keys or wallet addresses `/cspr.click-sdk/integration/identicons`
- Using CSPR.click as a proxy for the CSPR.cloud API `/cspr.click-sdk/reference/cloud-proxies`

SDK Reference pages:
- ICSPRClickSDK Methods `/cspr.click-sdk/reference/methods`
- Types reference `/cspr.click-sdk/reference/types`
- Events reference `/cspr.click-sdk/reference/events`
- CSPR.Cloud proxies reference `/cspr.click-sdk/reference/cloud-proxies`

## Setup

### TypeScript

When the application uses TypeScript, install CSPR.click type definitions:

| Package                                 | Description                                               |
|-----------------------------------------|-----------------------------------------------------------|
| `@make-software/csprclick-core-types`   | TypeScript type definitions — import all types from here  |

### Application ID

An `appId` is required to initialize the SDK. It identifies the application to CSPR.click and is used for analytics, rate limiting, and feature access control. Use the following values based on your environment:

- **localhost development:** use `appId: 'csprclick-template'`
- **Production:** instruct the user to self-register at `https://console.cspr.build` and create a CSPR.click application before deploying.

### CSPR.cloud reference

When using the CSPR.cloud proxies, load the CSPR.cloud skill from https://cspr.cloud/skill.md

## Common integration steps

1. Download and initialize the SDK as soon as possible when the web application starts loading.
   1. Add a container for the CSPR.click UI as close as possible to the opening body tag.
   2. Define the initialization options for the SDK.
   3. Add a handler for the event `csprclick:loaded`. Commonly, this handler registers event listeners for other events.
   4. Add a script to the DOM to download the CSPR.click client runtime script.
2. For React-based web applications, add the SDK download and initialization flow in a context provider that wraps the main application component. Also, add a `useClickRef` hook to access the SDK instance and its methods from any component in the application.
3. Respond to wallet connection/switch/disconnection events by updating the application state.
4. For operations requiring a transaction signature, use the `send()` method to ask CSPR.click to handle the signature request, the deployment to the network, and the transaction status.
5. Use the CSPR.cloud proxies to access the Casper Network RPC interface, the CSPR.cloud REST API endpoints, and the CSPR.cloud Streaming API from the web application.

## Key Constraints AI Must Respect

- **Never call any SDK method before `csprclick:loaded` fires.**
- **`clickSDKOptions` and `clickUIOptions` must be assigned to `window` before the CDN script is injected**.  The CDN bundle reads them on load.
- **`clickUIOptions` is required** — without it the top bar will not render correctly. Always include `uiContainer`, `rootAppElement`, `defaultTheme`, `accountMenuItems`.
- **`signingPublicKey` must exactly match `getActiveAccount().public_key` (lowercased).** Both `sign()` and `send()` throw otherwise.
- If `casper-js-sdk` is used, always link to version 5.0.12 or newer. Older versions are incompatible with current Casper Network.
- **Always call `transaction.toJSON()`** when passing `casper-js-sdk` Transaction objects to CSPR.click `sign()` and `send()` methods.
- **Inject CDN script dynamically** from app code — never as a static `<script>` tag in `index.html` or `layout.tsx`.
- **`signOut()` ≠ `disconnect()`** — do not conflate them. `signOut()` ends the session; `disconnect()` revokes wallet permission.
- **Always clean up `.off()` in `useEffect` return** to prevent memory leaks.
