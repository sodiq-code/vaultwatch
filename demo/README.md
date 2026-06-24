# VaultWatch Demo Video — Production Notes

## Output
- **Final video:** `vaultwatch_demo_v1.mp4` — 3:39, 6.2MB, 1280x720, H.264+AAC
- **Voiceover:** `voiceover_george.mp3` — George voice (ElevenLabs), 219.5s
- **Music:** `bg_music.mp3` — dark ambient cinematic, 220s, mixed at 12% under voiceover
- **Script:** `voiceover_script.txt` — ~450 words, 8 sections

## Video Structure / Timestamp Map
| Time | Section | Screen |
|------|---------|--------|
| 0:00–0:15 | Hook — "every second, billions move through DeFi" | Title card |
| 0:15–0:35 | Problem statement | Risk Intelligence overview |
| 0:35–1:05 | Solution — 3 layers | Risk Intelligence findings |
| 1:05–1:25 | Dashboard demo intro | Anomaly Detection |
| 1:25–2:05 | Live dashboard walkthrough | Audit Log (agent actions, TX hashes) |
| 2:05–2:35 | On-chain proof (8/8 contracts, 29 TX hashes) | Chain Status |
| 2:35–3:05 | Agent pipeline / SDK / MCP | Live Agent Feed |
| 3:05–3:39 | Launch plan + CTA | Risk Intelligence (outro) |

## Key Moments Judges Will See
- **Audit Log**: AuditAgent, RiskOracle, x402 payment, AgentBehaviorIndex, SafetyGuard — all live
- **Chain Status**: Block #8,279,455, 8/8 contracts deployed (Odra WASM · casper-test)
- **Live Feed**: 6 active agents, 8 on-chain contracts, streaming events every 3–5s
- **Risk Intelligence**: CRITICAL CasperSwap alert, HIGH CasperLend, HIGH CasperYield — real findings

## If You Want to Re-Edit
The video is built from static screenshots held as video slides — easy to replace/reorder.
Segment files: `seg_00.mp4` through `seg_07.mp4`

To swap a segment, generate a new `seg_XX.mp4` and re-run:
```bash
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy video_silent_new.mp4 -y
```
Then re-add audio with the same amix command in the build script.

## To Upload for DoraHacks
DoraHacks accepts YouTube/Vimeo links in the submission form.
Upload `vaultwatch_demo_v1.mp4` to YouTube (unlisted is fine) and paste the URL.

Alternatively, upload directly: DoraHacks supports direct video attachments up to ~100MB.

## Assets
- `title_card.png` — 1920x1088 title card (available for thumbnails)
- `screen_01_risk_intel_top.png` through `screen_06_livefeed.png` — 1280x720 dashboard screenshots
- `rec_chainstatus.mp4`, `rec_livefeed.mp4`, `rec_anomaly.mp4` — short live clips (~5-15s each)
