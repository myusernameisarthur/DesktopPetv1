# Phase 4 Report — Roll-over gesture built; hook features designed, deferred

Date: 2026-06-12 · Branch: `feature/phase-4-gesture` · Tag on merge: `phase-4-complete`

## Scope decision

Per the owner's direction (2026-06-11): the two OS-hook enablers — the global keyboard
activity listener (type-along) and the window event hook (bark-at-new-window) — were **not
built**. They are specified thoroughly in [PHASE-4-HOOKS-DESIGN.md](PHASE-4-HOOKS-DESIGN.md)
(APIs, threading, privacy guarantees, filtering, rate limiting, settings/HUD/test plans,
acceptance criteria, build order) for later development. Phase 4a — the roll-over mouse
gesture — needs no hook (pure cursor math) and was built.

## What was built (4a)

**`gestures.py` — `CircleGestureRecognizer`.** Armed by any click on the dog. Each tick it
takes the cursor's angle around the dog's center and accumulates the signed change; ~3
consistent loops (|accum| ≥ 3·360°) completes the gesture. Jitter and direction reversals
cancel; per-tick jumps > 90° are ignored; the cursor must stay in a 25–220 px ring (40-tick
grace); the arming window is ~11 s. Completion fires `ROLL_OVER` if the switch is on and the
dog is interruptible (SLEEPING / ALERT / EXCITED).

**`ROLL_OVER` state** (`ANIM: roll-over`, ~3.5 s one-shot): brief wobble in the lying pose,
then belly-up — body with a lighter belly patch, four paws paddling the air, head lolling
sideways with a flopped ear — then a wobble back and settle to SLEEPING. Reminders cannot
interrupt it (`_check_pending` refusal list); it uses the lying mask footprint.

**Plumbing:** settings key `command.roll_over` (default on) in a new **Command** menu group
("Roll over (click, then circle the dog 3x)"); `Test: roll over` force-fires; HUD gained a
`GESTURE` line — `-` when idle, `1.7/3 loops 8s` while armed.

## State → animation table

Unchanged from Phase 3 plus: **ROLL_OVER → roll-over**. (13 states now.)

## Verification (tools/verify_phase4.py — all PASS)

- Recognizer unit checks (synthetic coordinates): completes at 3.06 loops; 1.5 loops then
  reversing never completes (accumulation cancels); arming window times out; leaving the ring
  past the grace disarms.
- End-to-end with the **real cursor** (`SetCursorPos` driven in 3.4 circles after a synthesized
  dog click): ROLL_OVER fires; the HUD GESTURE line was observed live at `2.9/3 loops`.
- Belly-up frame screenshotted (`verify/phase4/roll-over-belly-up.png`); dog remains clickable
  during ROLL_OVER (Win32 `WindowFromPoint` probe); settles back to SLEEPING.
- Toggle off: the same full circling fires nothing; `Test: roll over` force-fires regardless.
- Phase 2 regression harness updated for the Command group (4 groups / 7 Test entries) — re-run
  clean. Exe rebuilt from spec and launch-checked.
- Log: `verify/phase4/phase4-log.txt`.

## What felt thin

- The roll-over's down/up transitions are a wobble + cut rather than a true rolling tween —
  acceptable procedurally; real art (Phase 6) should give the roll 3–4 dedicated frames each way.
- The gesture requires staying within 220 px of the dog; on a 4K screen that's a small ring.
  Revisit the radii against real usage when the hook features land.
- One harness lesson recorded for future tools: PyQt signal connections to bound methods are
  weak — keep Python references to helper objects driving QTimers.
