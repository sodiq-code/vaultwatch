"""
VaultWatch Demo Video Assembly Script
Total target: ~280s video
Screen recording: 92.86s (will be sliced and looped to cover narration)
Voiceover: 275.46s
Music: 280s
"""

import subprocess
import os

DEMO_DIR = "/home/user/vaultwatch/demo"
SCREEN_REC = "/home/user/Attachments/VaultWatch_—_DeFi_Risk_Intelligence_-_Google_Chrome_2026-06-24_11-27-20__haQPX.mov"
VOICE = f"{DEMO_DIR}/voiceover_raw.mp3"
MUSIC = f"{DEMO_DIR}/music_bg.mp3"
TITLE_CARD = f"{DEMO_DIR}/title_card.png"
OUTRO_CARD = f"{DEMO_DIR}/outro_card.png"
OUTPUT = f"{DEMO_DIR}/vaultwatch_demo_final.mp4"

# Target dimensions
W, H = 1280, 720

# ============================================================
# SECTION PLAN (start, end, recording_start, recording_end, label)
# The screen recording has these key sections:
#  0-10s  : Risk Intelligence - query + "Analyzing via Groq" 
#  10-20s : Agent Pipeline Findings (CRITICAL/HIGH findings)
#  20-30s : Anomaly Detection (score 42/100)
#  30-40s : RWA Assessment (APPROVED)
#  40-55s : Live Feed (all 8 contracts ON-CHAIN)
#  55-70s : Live Feed + findings
#  70-92s : Chain Status (block height, 8/8 contracts, deployer)
# ============================================================

sections = [
    # (video_start, video_end, source, rec_start, rec_end, label)
    # Title card - 8 seconds
    (0,   8,   "card",  0,    0,    ""),
    # Hook: The Problem (narration: 0-22s) — show Risk Intelligence tab
    (8,   30,  "rec",   0,    10,   "Risk Intelligence · Live Groq AI"),
    # Agent query in action (narration: 22-55s) — show query + findings
    (30,  65,  "rec",   0,    18,   "6 AI Agents · Real-Time Analysis"),
    # Pipeline findings (narration: 55-90s) — show full findings list
    (65,  100, "rec",   8,    22,   "Agent Pipeline Findings · On-Chain"),
    # Anomaly Detection (narration: 90-125s)
    (100, 135, "rec",   20,   30,   "Anomaly Detection · AnomalyAgent + SelfCorrectionAgent"),
    # RWA Assessment (narration: 125-160s)
    (135, 165, "rec",   30,   40,   "RWA Assessment · Institutional-Grade"),
    # Live Feed (narration: 160-200s)
    (165, 205, "rec",   40,   62,   "Live Feed · 6 Active Agents"),
    # Chain Status (narration: 200-245s)
    (205, 250, "rec",   62,   92,   "Chain Status · Verified On-Chain"),
    # Proof stats (narration: 235-260s) — repeat chain status
    (250, 265, "rec",   70,   85,   "29 TX Hashes · 130 Tests Passing"),
    # Outro card (narration: 260-275s)
    (265, 280, "card",  0,    0,    ""),
]

print("Section plan built successfully")
for s in sections:
    print(f"  [{s[0]}s-{s[1]}s] {s[5]}")

