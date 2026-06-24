import subprocess, os, json

DEMO_DIR = "/home/user/vaultwatch/demo"
SCREEN_REC = "/home/user/Attachments/VaultWatch_—_DeFi_Risk_Intelligence_-_Google_Chrome_2026-06-24_11-27-20__haQPX.mov"
VOICE = f"{DEMO_DIR}/voiceover_raw.mp3"
MUSIC = f"{DEMO_DIR}/music_bg.mp3"
TITLE_CARD = f"{DEMO_DIR}/title_card.png"
OUTRO_CARD = f"{DEMO_DIR}/outro_card.png"
OUTPUT = f"{DEMO_DIR}/vaultwatch_demo_final.mp4"
CLIPS_DIR = f"{DEMO_DIR}/clips"
os.makedirs(CLIPS_DIR, exist_ok=True)

W, H = 1280, 720

def run(cmd, label=""):
    print(f"  Running: {label or cmd[:80]}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ERROR: {r.stderr[-500:]}")
    return r.returncode == 0

# ============================================================
# Step 1: Extract/prepare video-only segments from screen recording
# Each segment = slice of recording, looped if needed, scaled to 1280x720
# ============================================================

# Font for section labels
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

segments_def = [
    # (clip_name, source, rec_start, rec_end, target_dur, label_text)
    ("01_title",    "card",  0,   0,   8,  ""),
    ("02_hook",     "rec",   0,   10,  22, "Risk Intelligence  |  LIVE GROQ AI"),
    ("03_query",    "rec",   0,   18,  35, "6 AI Agents  |  Real-Time Analysis"),
    ("04_findings", "rec",   8,   22,  35, "Agent Pipeline Findings  |  On-Chain"),
    ("05_anomaly",  "rec",   20,  30,  35, "Anomaly Detection  |  AnomalyAgent"),
    ("06_rwa",      "rec",   30,  40,  30, "RWA Assessment  |  Institutional-Grade"),
    ("07_livefeed", "rec",   40,  62,  40, "Live Feed  |  6 Active Agents  |  8 Contracts"),
    ("08_chain",    "rec",   62,  92,  45, "Chain Status  |  Verified On-Chain"),
    ("09_proof",    "rec",   70,  85,  15, "29 TX Hashes  |  130 Tests Passing"),
    ("10_outro",    "card",  0,   0,   15, ""),
]

clip_files = []

for name, src, rs, re, tdur, label in segments_def:
    out = f"{CLIPS_DIR}/{name}.mp4"
    clip_files.append(out)
    
    if src == "card":
        # Create static card video
        card_img = TITLE_CARD if "01" in name else OUTRO_CARD
        # Scale card to 1280x720 with padding
        cmd = (
            f'ffmpeg -y -loop 1 -i "{card_img}" -t {tdur} '
            f'-vf "scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1" '
            f'-c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -r 30 -an "{out}"'
        )
    else:
        # Extract slice from screen recording, loop if needed, scale to 1280x720
        slice_dur = re - rs
        # If slice_dur < tdur, loop it
        loop_count = max(1, int(tdur / slice_dur) + 2)
        
        # Draw label text at top of video if label exists
        label_filter = ""
        if label:
            # Escape special chars for drawtext
            safe_label = label.replace("'", "\\'").replace(":", "\\:")
            label_filter = (
                f",drawtext=fontfile={FONT}:text='{safe_label}'"
                f":fontsize=18:fontcolor=white:x=(w-text_w)/2:y=12"
                f":box=1:boxcolor=0x0D1B2A@0.88:boxborderw=10"
            )
        
        cmd = (
            f'ffmpeg -y -stream_loop {loop_count} -ss {rs} -i "{SCREEN_REC}" -t {tdur} '
            f'-vf "scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1{label_filter}" '
            f'-c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -r 30 -an "{out}"'
        )
    
    ok = run(cmd, f"Clip {name} ({tdur}s)")
    if ok:
        print(f"    ✓ {out}")
    else:
        print(f"    ✗ FAILED {name}")

print(f"\nAll clips ready: {len(clip_files)} files")
