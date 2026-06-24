"""Build final 2:20 VaultWatch demo video"""
import subprocess, os, glob

DEMO = "/home/user/vaultwatch/demo"
RAW = f"{DEMO}/raw_recordings"
CLIPS = f"{DEMO}/clips_v2"
os.makedirs(CLIPS, exist_ok=True)

SCREEN_REC = "/home/user/Attachments/VaultWatch_—_DeFi_Risk_Intelligence_-_Google_Chrome_2026-06-24_11-27-20__haQPX.mov"
TERMINAL   = f"{RAW}/terminal_raw.mp4"
TESTNET    = f"{RAW}/testnet_recording.mp4"
TITLE_IMG  = f"{DEMO}/title_card.png"
OUTRO_IMG  = f"{DEMO}/outro_card.png"
VOICE      = f"{DEMO}/voiceover_v2.mp3"
MUSIC      = f"{DEMO}/music_v2.mp3"
OUTPUT     = f"{DEMO}/vaultwatch_demo_v2.mp4"

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H = 1280, 720

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ERR: {r.stderr[-300:]}")
    return r.returncode == 0

def label_filter(text):
    if not text:
        return ""
    safe = text.replace("'", "\\'").replace(":", "\\:")
    return (
        f",drawtext=fontfile={FONT}:text='{safe}'"
        f":fontsize=16:fontcolor=white"
        f":x=(w-text_w)/2:y=10"
        f":box=1:boxcolor=0x000000@0.75:boxborderw=8"
    )

# ─────────────────────────────────────────────
# CLIP DEFINITIONS  (name, src, ss, dur, label)
# ss = seek offset in source; dur = output duration
# src: "title"|"outro"|"screen"|"testnet"|"terminal"
# ─────────────────────────────────────────────
clips = [
    # 0–7s   Title card
    ("01_title",    "title",    0,  7,  ""),
    # 7–22s  Dashboard: Risk Intelligence query (screen rec 0–15s)
    ("02_risk",     "screen",   0,  15, "Risk Intelligence  ·  Groq AI  ·  LIVE"),
    # 22–37s Dashboard: Agent findings (screen rec 8–22s)
    ("03_findings", "screen",   8,  15, "Agent Pipeline Findings  ·  On-Chain"),
    # 37–50s Dashboard: Anomaly Detection (screen rec 20–30s)
    ("04_anomaly",  "screen",   20, 13, "Anomaly Detection  ·  Score 42/100  ·  ELEVATED"),
    # 50–65s Dashboard: Live Feed all contracts on-chain (screen rec 40–55s)
    ("05_livefeed", "screen",   40, 15, "Live Feed  ·  6 Agents Active  ·  8 Contracts ON-CHAIN"),
    # 65–85s Testnet explorer
    ("06_testnet",  "testnet",  0,  20, "testnet.cspr.live  ·  Deployer Account  ·  Verified"),
    # 85–110s Terminal: pytest + pipeline
    ("07_terminal", "terminal", 0,  25, "pytest tests/ -v  ·  130/130 PASSED  ·  6 Agents Live"),
    # 110–115s Outro
    ("08_outro",    "outro",    0,  9,  ""),
]

clip_files = []
cumulative = 0

for name, src, ss, dur, lbl in clips:
    out = f"{CLIPS}/{name}.mp4"
    clip_files.append(out)
    lf = label_filter(lbl)

    if src == "title":
        cmd = (
            f'ffmpeg -y -loop 1 -i "{TITLE_IMG}" -t {dur} '
            f'-vf "scale={W}:{H}:force_original_aspect_ratio=decrease,'
            f'pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p" '
            f'-c:v libx264 -preset fast -crf 20 -r 30 -an "{out}"'
        )
    elif src == "outro":
        cmd = (
            f'ffmpeg -y -loop 1 -i "{OUTRO_IMG}" -t {dur} '
            f'-vf "scale={W}:{H}:force_original_aspect_ratio=decrease,'
            f'pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p" '
            f'-c:v libx264 -preset fast -crf 20 -r 30 -an "{out}"'
        )
    elif src == "screen":
        cmd = (
            f'ffmpeg -y -ss {ss} -i "{SCREEN_REC}" -t {dur} '
            f'-vf "scale={W}:{H}:force_original_aspect_ratio=decrease,'
            f'pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p{lf}" '
            f'-c:v libx264 -preset fast -crf 20 -r 30 -an "{out}"'
        )
    elif src == "testnet":
        # Slow down the testnet recording slightly (0.75x) so judges can read
        cmd = (
            f'ffmpeg -y -i "{TESTNET}" '
            f'-vf "setpts=1.5*PTS,scale={W}:{H}:force_original_aspect_ratio=decrease,'
            f'pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p{lf}" '
            f'-t {dur} '
            f'-c:v libx264 -preset fast -crf 20 -r 30 -an "{out}"'
        )
    elif src == "terminal":
        # Speed up terminal slightly to fit more content (1.2x)
        cmd = (
            f'ffmpeg -y -ss {ss} -i "{TERMINAL}" '
            f'-vf "setpts=0.75*PTS,scale={W}:{H}:force_original_aspect_ratio=decrease,'
            f'pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p{lf}" '
            f'-t {dur} '
            f'-c:v libx264 -preset fast -crf 20 -r 30 -an "{out}"'
        )

    ok = run(cmd)
    print(f"  {'✓' if ok else '✗'} [{cumulative}s–{cumulative+dur}s] {name} ({dur}s)")
    cumulative += dur

print(f"\nTotal: {cumulative}s = {cumulative/60:.1f} min")

# Write concat list
concat = f"{CLIPS}/concat.txt"
with open(concat, "w") as f:
    for cf in clip_files:
        f.write(f"file '{cf}'\n")

# Concatenate all clips
print("\nConcatenating clips...")
ok = run(
    f'ffmpeg -y -f concat -safe 0 -i "{concat}" '
    f'-c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p '
    f'"{DEMO}/video_v2_raw.mp4"'
)
print(f"  {'✓' if ok else '✗'} Concat done")

# Check actual video duration
r = subprocess.run(
    f'ffprobe -v quiet -show_format "{DEMO}/video_v2_raw.mp4"',
    shell=True, capture_output=True, text=True
)
for line in r.stdout.split('\n'):
    if 'duration' in line:
        print(f"  Video duration: {line.strip()}")

