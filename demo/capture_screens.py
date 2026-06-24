"""Capture testnet explorer + dashboard screens for video using playwright"""
from playwright.sync_api import sync_playwright
import time, os

OUT = "/home/user/vaultwatch/demo/raw_recordings"
os.makedirs(OUT, exist_ok=True)

TESTNET_URL = "https://testnet.cspr.live/account/0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116"
DASHBOARD_URL = "https://dashboard-rho-amber-89.vercel.app"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-gpu", "--window-size=1280,720"]
    )
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    page = ctx.new_page()

    # --- Testnet explorer screenshots ---
    print("Loading testnet explorer...")
    page.goto(TESTNET_URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    page.screenshot(path=f"{OUT}/testnet_deployer.png", full_page=False)
    print(f"  Saved testnet_deployer.png")

    # Scroll down to show deploy list
    page.evaluate("window.scrollBy(0, 400)")
    time.sleep(1)
    page.screenshot(path=f"{OUT}/testnet_deploys.png", full_page=False)
    print(f"  Saved testnet_deploys.png")

    # --- Dashboard screenshots ---
    print("Loading dashboard...")
    page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    page.screenshot(path=f"{OUT}/dashboard_main.png", full_page=False)
    print(f"  Saved dashboard_main.png")

    # Try to click Risk Intelligence tab
    try:
        page.click("text=Risk Intelligence", timeout=5000)
        time.sleep(2)
        page.screenshot(path=f"{OUT}/dashboard_risk.png", full_page=False)
        print(f"  Saved dashboard_risk.png")
    except:
        print("  Risk tab click failed - continuing")

    # Try Chain Status
    try:
        page.click("text=Chain Status", timeout=5000)
        time.sleep(2)
        page.screenshot(path=f"{OUT}/dashboard_chain.png", full_page=False)
        print(f"  Saved dashboard_chain.png")
    except:
        print("  Chain tab click failed - continuing")

    browser.close()

print("Done!")
