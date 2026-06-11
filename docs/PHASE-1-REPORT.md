# Phase 1 Report — Idle micro-behavior engine + fidget catalogs

Date: 2026-06-11 · Branch: `feature/phase-1-idle-engine` · Tag on merge: `phase-1-complete`

## What was built

**`fidgets.py`** — the variability engine. A fidget is a short motion that plays without
changing `self.state`: the dog stays SLEEPING/ALERT, the drawing gets a brief additive delta.

- **Irregular timing:** gap to the next fidget rolled uniformly per pose — 4–12 s lying,
  3–8 s standing (ALERT fidgets a little more often as part of its signature). Never a beat.
- **Weighting:** common=6, medium=3, rare=1, weighted random over the current pose's catalog.
- **No-repeat memory:** the last 2 fidgets are excluded from the next draw.
- **Per-fidget cooldown:** each fidget also has its own re-use cooldown (8–60 s).
- **One at a time, never over a behavior:** the engine only runs in SLEEPING (lying) and
  ALERT (standing); any pose/state change cancels the active fidget instantly, so a fidget can
  never touch a locked one-shot (stretch, scratch, drink…) or a walk.
- **`rate_mult`** — the single hook for future modulators (energy, time of day). Default 1.0.

**Catalogs** (drawn as deltas inside `_draw_sleeping` / `_draw_standing` / `_draw`):

| Lying (SLEEPING) | dur | rarity | Standing (ALERT) | dur | rarity |
|---|---|---|---|---|---|
| ear-flick | 0.3s | common | blink | 0.2s | common |
| nose-twitch | 0.25s | common | ear-swivel | 0.4s | common |
| tail-twitch | 0.3s | common | weight-shift | 0.5s | common |
| sigh (+z puff) | 1.2s | medium | head-tilt | 0.8s | medium |
| dream-kick | 0.6s | medium | look-around | 1.0s | medium |
| eye-crack | 0.5s | medium | wag-burst | 0.7s | medium |
| resettle | 1.0s | rare | shake-off (stress shake) | 0.8s | rare |
| scratch (folded into idle roll) | 1.2s | rare | bone-chew (from pocket) | 3.0s | rare |
| | | | sit | 2.0s | rare |

**ALERT re-signature** (no longer reads as a paused walk): ears pricked up (taller, higher),
tail does a gentle slow sway instead of the full walk-speed wag (full wag now only when
walking/excited or during the wag-burst fidget), and the busier 3–8 s fidget cadence.

**HUD:** new `FIDGET` line (name + seconds remaining, `-` when idle) between ANIM and PHASE.

## State → animation table (unchanged this phase — fidgets are stateless layers)

| State | ANIM | | State | ANIM |
|---|---|---|---|---|
| SLEEPING | breathing | | STRETCHING | stretch |
| ALERT | alert-stand | | DRINKING | drink |
| WALKING | trot | | TASK_RETURN | trot |
| EXCITED | bounce | | SCRATCHING | scratch |
| FETCHING | trot | | CHEWING | chew |
| RETURNING_BALL | trot-carry | | SNIFF_WALK | sniff |

Fidgets appear on the HUD's FIDGET line, not as states. The shared-trot tell is Phase 3.

## Verification (tools/verify_phase1.py — automated harness on the real app)

- **All 17 fidgets force-fired** in their correct pose; each confirmed active at its midpoint
  with the state unchanged (SLEEPING/ALERT). Screenshot per fidget in `verify/phase1/`.
- **Accelerated idle soak** (rate_mult=6): lying 45 s → 15 fidgets, 9 distinct, zero
  back-to-back repeats, gaps 1.7–5.3 s (irregular); standing 30 s → 11 fidgets, 7 distinct,
  zero repeats. (One 716 s "gap" in the log is a monotonic-clock sampling artifact — the
  remaining 23 samples sum correctly to their soak windows.)
- **Click-through probed via Win32 `WindowFromPoint`:** point on the dog hits the overlay;
  point on the empty strip passes through to the desktop; point on the HUD passes through. ✔
- **Idle CPU:** 3.8% of one core over 10 s at ~30 Hz. Reasonable.
- **Exe rebuilt** from `Biscuit.spec` (PyInstaller 6.20); launches, dog renders, fidget module
  bundled (`verify/phase1/exe-launch.png`).
- Full log: `verify/phase1/phase1-log.txt`.

Key screenshots: `lying-baseline`, `standing-alert-baseline` (ears up, calm tail),
`standing-sit` (rear visibly drops), `standing-bone-chew` (bone at mouth), `lying-scratch`,
`standing-shake-off`, `lying-sigh`.

## What felt thin

- **head-tilt / look-around** read as small head shifts rather than a true tilt/turn — the
  procedural head is a circle, so rotation barely shows. Real art (Phase 6) will carry these.
- **ear-swivel** is subtle to the point of blink-and-miss; acceptable as a "common" texture.
- **sit** works but the rotated body ellipse is approximate; fine for a rare fidget,
  worth a dedicated pose when art lands.
- Standing fidgets only ever show in ALERT (cursor near), so a user who never mouses near the
  dog never sees them. If Phase 5 adds standing idle moments, the engine already supports it.
