// CSPR.click Web SDK — React integration for the VaultWatch dashboard.
//
// Implements the official "Common integration steps" from the CSPR.click AI
// Agent Skill (vaultwatch/skills/csprclick-skill/SKILL.md) and mirrors the
// reference React Context Provider documented at:
//   https://docs.cspr.click/cspr.click-sdk/integration/react-context-provider
//
// Key constraints enforced here (see SKILL.md "Key Constraints AI Must Respect"):
//   * `clickSDKOptions` and `clickUIOptions` are assigned to `window` BEFORE
//     the CDN script is injected (the bundle reads them on load).
//   * `clickUIOptions` is required and includes uiContainer, rootAppElement,
//     defaultTheme and accountMenuItems.
//   * The CDN script is injected DYNAMICALLY — never as a static <script> tag.
//   * No SDK method is called before the `csprclick:loaded` window event fires.
//   * All `.on()` registrations are cleaned up with `.off()` in useEffect
//     return to prevent memory leaks.
//
// Note on event names: the SKILL.md brief mentions a `csprclick:activeAccountChanged`
// event. The official Events reference (https://docs.cspr.click/cspr.click-sdk/reference/events)
// does not list that event — instead CSPR.click emits the granular events
// `csprclick:signed_in`, `csprclick:switched_account`,
// `csprclick:unsolicited_account_change`, `csprclick:signed_out` and
// `csprclick:disconnected`. `useActiveAccount()` therefore listens to that
// granular set so the dashboard's connected-account state stays correct across
// every connection / switch / disconnect lifecycle. This deviation is
// documented in the worklog.
//
// Note on the connect() provider key: the task brief says to call
// `clickRef.connect('CasperWallet')`, but the official Types reference
// (https://docs.cspr.click/cspr.click-sdk/reference/types) defines the
// canonical provider string for the Casper Wallet extension as
// `WALLET_KEYS.CASPER_WALLET === 'casper-wallet'`. We therefore use
// `'casper-wallet'` for both the `providers` list and the `connect()` call so
// the integration actually works at runtime.

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  createElement,
} from 'react'

// ---------------------------------------------------------------------------
// Constants — string equivalents of the @make-software/csprclick-core-types
// enums (the dashboard is plain JS and does not ship the type package).
// Source: https://docs.cspr.click/cspr.click-sdk/reference/types
// ---------------------------------------------------------------------------

export const WALLET_KEYS = {
  CASPER_WALLET: 'casper-wallet',
  LEDGER: 'ledger',
  METAMASK_SNAP: 'metamask-snap',
}

export const CONTENT_MODE = {
  IFRAME: 'iframe',
  POPUP: 'popup',
}

// CSPR.click CDN runtime. Verified from the official "Download and initialize"
// doc page: https://docs.cspr.click/cspr.click-sdk/integration/download-and-initialize
const CSPRCLICK_CDN_URL = 'https://cdn.cspr.click/ui/v2.1.0/csprclick-client-2.1.0.js'
const CSPRCLICK_SCRIPT_ID = 'csprclick-client'

// ---------------------------------------------------------------------------
// Pre-load window options.
//
// The CDN bundle reads `window.clickUIOptions` and `window.clickSDKOptions`
// synchronously when it executes, so they MUST exist on `window` before the
// <script> tag is appended to the DOM. Assigning them at module-evaluation
// time guarantees they are in place before any component mounts.
// ---------------------------------------------------------------------------

if (typeof window !== 'undefined') {
  if (!window.clickUIOptions) {
    // `clickUIOptions` is REQUIRED — without it the top bar does not render
    // correctly. (SKILL.md "Key Constraints AI Must Respect".)
    window.clickUIOptions = {
      // DOM id where CSPR.click mounts the top bar + modal UI.
      // Matches <div id="csprclick-ui"></div> in index.html.
      uiContainer: 'csprclick-ui',
      // Selector of the React root — used by CSPR.click to scope modal overlays.
      rootAppElement: 'root',
      // Match the dashboard's dark theme.
      defaultTheme: 'dark',
      // Top-bar account dropdown menu items, in display order.
      accountMenuItems: [
        'AccountCardMenuItem',
        'CopyHashMenuItem',
        'BuyCSPRMenuItem',
      ],
      // Render the official CSPR.click top bar (so the SDK-managed wallet
      // button is available in addition to our custom WalletBar).
      showTopBar: true,
      show1ClickModal: true,
    }
  }

  if (!window.clickSDKOptions) {
    window.clickSDKOptions = {
      appName: 'VaultWatch',
      // Sanctioned localhost appId per SKILL.md "Application ID" section.
      appId: 'csprclick-template',
      contentMode: CONTENT_MODE.IFRAME,
      // Casper testnet — VaultWatch runs against casper-test.
      chainName: 'casper-test',
      providers: [
        WALLET_KEYS.CASPER_WALLET,
        WALLET_KEYS.LEDGER,
        WALLET_KEYS.METAMASK_SNAP,
      ],
    }
  }
}

// ---------------------------------------------------------------------------
// React Context
// ---------------------------------------------------------------------------

const ClickContext = createContext(null)

/**
 * Truncates a Casper public key for display, e.g.
 *   "0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7"
 *      -> "0203…e3db"
 * Falls back to the full string if it is too short to truncate.
 */
export function truncatePublicKey(pk, head = 4, tail = 4) {
  if (!pk || typeof pk !== 'string') return ''
  if (pk.length <= head + tail + 1) return pk
  return `${pk.slice(0, head)}…${pk.slice(-tail)}`
}

/**
 * CSPRClickProvider wraps the application and:
 *   1. Ensures `window.clickUIOptions` / `window.clickSDKOptions` exist
 *      (assigned above at module-eval time).
 *   2. Listens for the `csprclick:loaded` window event.
 *   3. On load, stores the SDK ref in state and registers SDK-level event
 *      listeners (`ref.on(...)`) for account lifecycle events.
 *   4. Reconciles the initial active account via `getActiveAccountAsync()`.
 *   5. Injects the CDN script tag (idempotent — guarded by script id check).
 *   6. Cleans up every listener in the useEffect return (`.off()` +
 *      `removeEventListener`) to prevent memory leaks.
 *
 * Children read the SDK ref and active account via `useClickRef()` and
 * `useActiveAccount()`.
 */
export function CSPRClickProvider({ children }) {
  const [clickRef, setClickRef] = useState(null)
  const [activeAccount, setActiveAccount] = useState(null)

  useEffect(() => {
    let ref = null

    // Reconcile the active account on SDK load and whenever a sign-in / switch
    // event fires. `withBalance` is optional but cheap — keeps the WalletBar
    // able to show CSPR balance in the future without a re-fetch.
    const syncActiveAccount = async (sdkRef) => {
      try {
        const account = await sdkRef.getActiveAccountAsync({
          withBalance: true,
          withFiatCurrency: 'USD',
        })
        setActiveAccount(account && account.public_key ? account : null)
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('[csprclick] getActiveAccountAsync failed:', err)
        setActiveAccount(null)
      }
    }

    // ---- SDK-level event handlers (registered via ref.on) -----------------
    const onSignedIn = (evt) => {
      const account = evt && evt.account
      setActiveAccount(account && account.public_key ? account : null)
    }
    const onSwitchedAccount = (evt) => {
      const account = evt && evt.account
      setActiveAccount(account && account.public_key ? account : null)
    }
    const onUnsolicitedAccountChange = (evt) => {
      const account = evt && evt.account
      setActiveAccount(account && account.public_key ? account : null)
    }
    const onSignedOut = () => setActiveAccount(null)
    const onDisconnected = () => setActiveAccount(null)

    // ---- Window-level load handler ---------------------------------------
    const handleSdkLoaded = () => {
      ref = window.csprclick
      if (!ref) {
        // eslint-disable-next-line no-console
        console.warn('[csprclick] csprclick:loaded fired but window.csprclick is undefined')
        return
      }

      setClickRef(ref)

      // Register SDK event listeners. These MUST be torn down with `.off()`
      // to avoid leaking handlers across HMR / unmount.
      ref.on('csprclick:signed_in', onSignedIn)
      ref.on('csprclick:switched_account', onSwitchedAccount)
      ref.on('csprclick:unsolicited_account_change', onUnsolicitedAccountChange)
      ref.on('csprclick:signed_out', onSignedOut)
      ref.on('csprclick:disconnected', onDisconnected)

      // Reconcile any pre-existing session (e.g. page refresh with the wallet
      // still connected).
      syncActiveAccount(ref)
    }

    window.addEventListener('csprclick:loaded', handleSdkLoaded)

    // If the CDN script beat React to the punch (unlikely in this app but
    // defensive), reconcile immediately.
    if (window.csprclick) {
      handleSdkLoaded()
    }

    // ---- Dynamically inject the CDN script (idempotent) ------------------
    // SKILL.md: "Inject CDN script dynamically from app code — never as a
    // static <script> tag".
    if (!document.querySelector(`script#${CSPRCLICK_SCRIPT_ID}`)) {
      const script = document.createElement('script')
      script.src = CSPRCLICK_CDN_URL
      script.id = CSPRCLICK_SCRIPT_ID
      script.async = true
      document.head.appendChild(script)
    }

    // ---- Cleanup ---------------------------------------------------------
    return () => {
      window.removeEventListener('csprclick:loaded', handleSdkLoaded)
      if (ref && typeof ref.off === 'function') {
        ref.off('csprclick:signed_in', onSignedIn)
        ref.off('csprclick:switched_account', onSwitchedAccount)
        ref.off('csprclick:unsolicited_account_change', onUnsolicitedAccountChange)
        ref.off('csprclick:signed_out', onSignedOut)
        ref.off('csprclick:disconnected', onDisconnected)
      }
    }
  }, [])

  // Memoize the context value shape so consumers don't need to know about the
  // internal `activeAccount` object layout.
  const value = {
    clickRef,
    // `null` until the CDN runtime fires `csprclick:loaded`.
    isLoaded: clickRef !== null,
    // Active account shape: { public_key, provider, name?, balance?, ... }
    activeAccount,
    publicKey: activeAccount?.public_key ?? null,
    provider: activeAccount?.provider ?? null,
  }

  return createElement(
    ClickContext.Provider,
    { value },
    children,
  )
}

/**
 * useClickRef — returns the CSPR.click SDK ref (or `null` until the
 * `csprclick:loaded` event fires). Mirrors the official hook name from the
 * React Context Provider doc.
 *
 * NEVER call any method on the returned ref while it is `null` — the SKILL.md
 * constraint "Never call any SDK method before `csprclick:loaded` fires" still
 * applies. Consumers should guard with `if (!clickRef) return`.
 */
export function useClickRef() {
  const ctx = useContext(ClickContext)
  if (!ctx) {
    throw new Error('useClickRef must be used within a <CSPRClickProvider>')
  }
  return ctx
}

/**
 * useActiveAccount — convenience hook returning the active wallet account
 * ({ public_key, provider, ... }) or `null` when no wallet is connected.
 *
 * Internally the provider already tracks `csprclick:signed_in`,
 * `csprclick:switched_account`, `csprclick:unsolicited_account_change`,
 * `csprclick:signed_out` and `csprclick:disconnected` events, so this hook is
 * a thin selector over the provider's state — it does not register any
 * additional listeners.
 *
 * (The SKILL.md brief names a `csprclick:activeAccountChanged` event; the
 * official Events reference does not define that event name, so the provider
 * listens to the granular event set instead. See the header comment.)
 */
export function useActiveAccount() {
  const ctx = useContext(ClickContext)
  if (!ctx) {
    throw new Error('useActiveAccount must be used within a <CSPRClickProvider>')
  }
  return ctx.activeAccount
}

// ---------------------------------------------------------------------------
// Helpers exposed for the WalletBar / other components
// ---------------------------------------------------------------------------

/**
 * Open the CSPR.click wallet selector for a specific provider.
 *
 * We call `connect('casper-wallet')` (the canonical `WALLET_KEYS.CASPER_WALLET`
 * value) rather than the literal `'CasperWallet'` from the task brief — see
 * the header comment for rationale. If the SDK ref is not yet loaded, this is
 * a no-op.
 */
export function connectCasperWallet(ref) {
  if (!ref) return
  try {
    // `connect()` returns a Promise<AccountType|undefined> but the actual
    // account state arrives via the `csprclick:signed_in` event, which the
    // provider already listens to. We still await to surface errors.
    const result = ref.connect(WALLET_KEYS.CASPER_WALLET)
    if (result && typeof result.catch === 'function') {
      result.catch((err) => {
        // eslint-disable-next-line no-console
        console.error('[csprclick] connect(casper-wallet) failed:', err)
      })
    }
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[csprclick] connect threw:', err)
  }
}

/**
 * Disconnect the active wallet. Per SKILL.md "signOut() ≠ disconnect()":
 *   * `signOut()` ends the session (wallet may reconnect silently next time).
 *   * `disconnect()` revokes the wallet's connection permission.
 *
 * The WalletBar's "Disconnect" button uses `disconnect()` so the user must
 * re-authorize the wallet on the next connect — matching the SKILL.md guidance
 * for a Disconnect button.
 */
export function disconnectWallet(ref) {
  if (!ref) return
  try {
    // Empty args => disconnect from the currently active account/wallet.
    const result = ref.disconnect()
    if (result && typeof result.catch === 'function') {
      result.catch((err) => {
        // eslint-disable-next-line no-console
        console.error('[csprclick] disconnect failed:', err)
      })
    }
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[csprclick] disconnect threw:', err)
  }
}

// Re-export the helpers as a stable callback-friendly API for consumers that
// prefer not to import individual functions.
export function useCSPRClickActions() {
  const { clickRef } = useClickRef()
  return {
    connect: useCallback(() => connectCasperWallet(clickRef), [clickRef]),
    disconnect: useCallback(() => disconnectWallet(clickRef), [clickRef]),
  }
}
