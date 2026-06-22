#!/usr/bin/env python3
"""
VaultWatch — Playwright Demo Recorder
Automatically opens the VaultWatch dashboard, runs through all demo flows,
and records the session as a video.
"""

from __future__ import annotations

import os
import sys
import asyncio
import logging
import subprocess
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("record_demo")

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:5173")
API_URL = os.getenv("API_URL", "http://localhost:8000")
VIDEO_DIR = Path(os.getenv("VIDEO_DIR", "demo_assets/recordings"))
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "demo_assets/screenshots"))


async def record_demo() -> None:
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        logger.error("playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Starting demo recording...")
    logger.info("Dashboard: %s | API: %s", DASHBOARD_URL, API_URL)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(VIDEO_DIR),
            record_video_size={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        try:
            # --- Scene 1: Dashboard load ---
            logger.info("Scene 1: Loading dashboard...")
            await page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=15_000)
            await page.wait_for_timeout(1500)
            await page.screenshot(path=str(SCREENSHOT_DIR / "01_dashboard.png"))
            logger.info("Screenshot: 01_dashboard.png")

            # --- Scene 2: Risk query ---
            logger.info("Scene 2: Risk intelligence query...")
            query_input = page.locator('[data-testid="risk-query-input"], input[placeholder*="risk"], input[placeholder*="query"]')
            if await query_input.count() > 0:
                await query_input.first.fill("What is the current risk level for CasperSwap?")
                await page.wait_for_timeout(500)
                submit_btn = page.locator('[data-testid="query-submit"], button[type="submit"], button:has-text("Analyze")')
                if await submit_btn.count() > 0:
                    await submit_btn.first.click()
                    await page.wait_for_timeout(3000)
            else:
                # Navigate directly to risk section
                risk_nav = page.locator('nav a:has-text("Risk"), a:has-text("Intelligence")')
                if await risk_nav.count() > 0:
                    await risk_nav.first.click()
                    await page.wait_for_timeout(1000)

            await page.screenshot(path=str(SCREENSHOT_DIR / "02_risk_query.png"))
            logger.info("Screenshot: 02_risk_query.png")

            # --- Scene 3: Anomaly detection ---
            logger.info("Scene 3: Anomaly detection...")
            anomaly_nav = page.locator('nav a:has-text("Anomaly"), a:has-text("Detection")')
            if await anomaly_nav.count() > 0:
                await anomaly_nav.first.click()
                await page.wait_for_timeout(1000)
            await page.wait_for_timeout(1500)
            await page.screenshot(path=str(SCREENSHOT_DIR / "03_anomaly.png"))
            logger.info("Screenshot: 03_anomaly.png")

            # --- Scene 4: RWA assessment ---
            logger.info("Scene 4: RWA assessment...")
            rwa_nav = page.locator('nav a:has-text("RWA"), a:has-text("Assets")')
            if await rwa_nav.count() > 0:
                await rwa_nav.first.click()
                await page.wait_for_timeout(1000)
            await page.wait_for_timeout(1500)
            await page.screenshot(path=str(SCREENSHOT_DIR / "04_rwa.png"))
            logger.info("Screenshot: 04_rwa.png")

            # --- Scene 5: Audit log ---
            logger.info("Scene 5: Audit log...")
            audit_nav = page.locator('nav a:has-text("Audit"), a:has-text("Log")')
            if await audit_nav.count() > 0:
                await audit_nav.first.click()
                await page.wait_for_timeout(1000)
            await page.wait_for_timeout(1500)
            await page.screenshot(path=str(SCREENSHOT_DIR / "05_audit.png"))
            logger.info("Screenshot: 05_audit.png")

            # --- Scene 6: Chain status ---
            logger.info("Scene 6: Chain status...")
            chain_nav = page.locator('nav a:has-text("Chain"), a:has-text("Status")')
            if await chain_nav.count() > 0:
                await chain_nav.first.click()
                await page.wait_for_timeout(1000)
            await page.wait_for_timeout(2000)
            await page.screenshot(path=str(SCREENSHOT_DIR / "06_chain.png"))
            logger.info("Screenshot: 06_chain.png")

            logger.info("All scenes recorded!")

        except Exception as exc:
            logger.error("Recording error: %s", exc)
            await page.screenshot(path=str(SCREENSHOT_DIR / "error_state.png"))
            raise

        finally:
            await context.close()
            await browser.close()

    # Find the recorded video
    videos = list(VIDEO_DIR.glob("*.webm"))
    if videos:
        video_path = videos[-1]
        logger.info("Video recorded: %s", video_path)

        # Convert to mp4 if ffmpeg is available
        mp4_path = VIDEO_DIR / "vaultwatch_demo.mp4"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(video_path), "-c:v", "libx264", str(mp4_path)],
                check=True,
                capture_output=True,
            )
            logger.info("Converted to MP4: %s", mp4_path)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffmpeg not available — keeping .webm format")
    else:
        logger.warning("No video file found in %s", VIDEO_DIR)


if __name__ == "__main__":
    asyncio.run(record_demo())
