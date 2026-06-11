# Phase 3 Report — Distinct gaits

Date: 2026-06-11 · Branch: `feature/phase-3-gaits` · Tag on merge: `phase-3-complete`

## What was built

A `Gait` parameter table in biscuit.py — locomotion is no longer one hard-coded trot. Each gait
authors speed (px/tick), leg-cycle rate (`walk_phase` increment), leg swing amplitude,
whole-body bounce, head-down offset, and tail-wag amplitude; `STATE_GAIT` routes each travelling
state to its gait, and `_active_gait()` is phase-aware (a drink/pickup/sniff pause reports no
gait, so the leg cycle idles during pauses).

| Gait | speed px/tick | phase rate | swing | bounce | head | wag | Used by |
|---|---|---|---|---|---|---|---|
| trot-brisk | 1.5 | 0.25 | 5 | – | – | 12 | WALKING, DRINKING approach |
| plod | 0.9 | 0.15 | 3 | – | 3 down | 6 | TASK_RETURN, RETURNING_BALL |
| scamper | 2.6 | 0.42 | 7 | 2.5 | – | 14 | FETCHING |
| sniff-walk | 0.75 | 0.12 | 3 | – | 8 (existing nose-down) | 4 | SNIFF_WALK |

Feel: the plod travels slow, head slightly low, lazy half-wag — "heading home". The scamper is
fast with short quick strides and the dog visibly bounces off the ground — "going for the ball".
The sniff-walk keeps its nose-down pose and pause-and-go but now also has a slower, smaller leg
cycle. The carried ball rides at the plod's lowered mouth height.

## State → animation table (as it now stands)

| State | ANIM | | State | ANIM |
|---|---|---|---|---|
| SLEEPING | breathing | | STRETCHING | stretch |
| ALERT | alert-stand | | DRINKING | drink |
| WALKING | **trot-brisk** | | TASK_RETURN | **plod** |
| EXCITED | bounce | | SCRATCHING | scratch |
| FETCHING | **scamper** | | CHEWING | chew |
| RETURNING_BALL | **plod-carry** | | SNIFF_WALK | **sniff-walk** |

The HUD ANIM line reports these labels live (bold = changed this phase). No two locomotion
states share an animation label anymore.

## Verification (tools/verify_phase3.py — all PASS)

- Each locomotion state forced on the real app; measured travel speed and leg-cycle rate match
  the authored gait exactly (1.50/0.90/2.60/0.75 px/tick; phase rates 0.25/0.15/0.42/0.12),
  and the HUD ANIM label is correct per state. Mid-stride screenshot per gait in
  `verify/phase3/`.
- Measured gait speeds are distinct and ordered: scamper > trot-brisk > plod > sniff-walk.
- Sniff-walk pause-and-go confirmed still firing; forced TASK_RETURN completes back to
  SLEEPING on the bed (end-to-end return path intact).
- Exe rebuilt from the spec and launches.
- Log: `verify/phase3/phase3-log.txt`.

## Notes / what felt thin

- **Effective tick rate is ~21 Hz, not the nominal 30 Hz** — Windows coalesces the 33 ms QTimer
  to ~47 ms at default timer resolution. All speeds/durations in the app are effectively tuned
  to this and it's uniform across the app, so nothing is wrong on screen; but it's worth a
  Phase 7 decision (Qt.PreciseTimer would speed *everything* up ~40% and change the tuned feel,
  so it was deliberately not flipped mid-phase). The verify harness measures in per-tick units
  for this reason.
- DRINKING's approach reuses trot-brisk rather than an "ease-to-stop" approach gait (the
  behavior map's minimum cut). An approach gait is a candidate for Phase 5/7 polish.
- Scamper bounce momentarily lifts all four feet off the taskbar — reads as bouncy and
  intentional at this art level; revisit with real art.
