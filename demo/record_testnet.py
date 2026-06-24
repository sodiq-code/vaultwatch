"""Record testnet explorer as video using playwright"""
from playwright.sync_api import sync_playwright
import time, os

OUT = "/home/user/vaultwatch/demo/raw_recordings"

TESTNET_URL = "https://testnet.cspr.live/account/0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-gpu"]
    )
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 720},
        record_video_dir=OUT,
        record_video_size={"width": 1280, "height": 720}
    )
    page = ctx.new_page()

    print("Navigating to testnet explorer...")
    page.goto(TESTNET_URL, wait_until="networkidle", timeout=30000)
    time.sleep(2)
    
    # Dismiss cookie banner if present
    try:
        page.click("text=Accept", timeout=3000)
        time.sleep(1)
    except:
        pass

    # Stay on account overview for 5 seconds
    time.sleep(5)

    # Scroll down to show activity/transactions
    page.evaluate("window.scrollBy(0, 350)")
    time.sleep(5)

    # Click Published contracts tab to show deployed contracts
    try:
        page.click("text=Published contracts", timeout=5000)
        time.sleep(4)
    except:
        print("  No Published contracts tab, scrolling more")
        page.evaluate("window.scrollBy(0, 300)")
        time.sleep(4)

    # Click Transactions tab
    try:
        page.click("text=Transactions", timeout=5000)
        time.sleep(4)
    except:
        pass

    # Final: go back to general/activity view
    try:
        page.click("text=General", timeout=3000)
        time.sleep(3)
    except:
        time.sleep(3)

    ctx.close()
    browser.close()

# Rename the recorded video
import glob
videos = glob.glob(f"{OUT}/*.webm")
if videos:
    latest = max(videos, key=os.path.getmtime)
    dest = f"{OUT}/testnet_recording.webm"
    os.rename(latest, dest)
    print(f"Saved: {dest}")
    import subprocess
    subprocess.run([
        "ffmpeg", "-y", "-i", dest,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "30",
        f"{OUT}/testnet_recording.mp4"
    ], capture_output=True)
    print(f"Converted to MP4")
else:
    print("No video recorded!")

print("Done!")
