# Phase 5 Report — Remaining behaviors; the list is FROZEN

Date: 2026-06-12 · Branch: `feature/phase-5-behaviors` · Tag on merge: `phase-5-complete`

## What was built

Four behaviors complete the catalog (17 states total):

- **BARKING** (`bark`, ~1.2 s): head tips back with a small body recoil, mouth opens on each of
  two bobs. Fired today by Test and as greet's flourish; the deferred window-bark detector
  (PHASE-4-HOOKS-DESIGN.md) will call the same `_start_bark()` — the animation half of 4c is
  done in advance.
- **BEG** (`beg-sit-up`, ~2.4 s): **double-click the dog**. Rear stays planted and sinks
  slightly, torso tilts up ~38° around the rear hip, head rides the raised front, front paws
  dangle with a tiny paddle, tongue at full lift, tail sweeps the ground. Switch: `command.beg`.
- **GREETING** (`greet-wag`, ~2.6 s): little hops with tongue and full-speed wag (shares the
  excited flair), 50% chance to finish with a bark. Fires (a) ~1.8 s after launch and (b) when
  the cursor moves again after being still for 10+ minutes — detected from the cursor position
  the app already polls each tick, **no hooks** — rate-limited to one return-greet per 10 min.
  Switch: `reactive.greet`.
- **ZOOMIES** (`dash`, rare): a new fifth gait (3.4 px/tick, fastest cycle, biggest bounce);
  3–5 flat-out dashes back and forth across the taskbar, then a spent plod home (TASK_RETURN).
  Joins the ambient picker with weight 1 vs 3 for walk/scratch/chew/sniff. Switch: `idle.zoomies`.

Bark, beg, and greet joined the reminder-refusal list (one-shots can't be interrupted by
stretch/water; the pending reminder fires after). Zoomies, like the other ambient idles, stays
interruptible. The menu gained a **Reactive** group, Command grew to two entries, Idle to seven;
the Test section now has 11 entries (bark/beg/greet/zoomies added). The launch greet is a named
stoppable timer so test harnesses can exclude it.

## State → animation table (final, frozen)

| State | ANIM | | State | ANIM |
|---|---|---|---|---|
| SLEEPING | breathing | | TASK_RETURN | plod |
| ALERT | alert-stand | | SCRATCHING | scratch |
| WALKING | trot-brisk | | CHEWING | chew |
| EXCITED | bounce | | SNIFF_WALK | sniff-walk |
| FETCHING | scamper | | ROLL_OVER | roll-over |
| RETURNING_BALL | plod-carry | | **BARKING** | **bark** |
| STRETCHING | stretch | | **BEG** | **beg-sit-up** |
| DRINKING | drink | | **GREETING** | **greet-wag** |
| | | | **ZOOMIES** | **dash** |

## Verification (tools/verify_phase5.py — 16 checks, all PASS)

- Bark/beg/greet fire, render (screenshots in `verify/phase5/`), and settle back to SLEEPING.
- Beg fires from a **real double-click event**, honors `command.beg`, Test bypasses the switch,
  and a stretch reminder cannot interrupt it (stays pending).
- Greet fires on the launch path; the bark chain was forced and observed; the switch disables
  it; the **idle-return** trigger fired on a cursor move after a (back-dated) idle gap and was
  then suppressed by the cooldown. (Test note: the original test held the cursor still in real
  time and failed because a human was using the mouse — rewritten to back-date the last-move
  timestamp, which also documents the mechanism.)
- Zoomies: measured 3.40 px/tick (authored 3.4), hands off to TASK_RETURN, and is reachable
  through the ambient picker.
- Phase 1–4 harnesses re-run as regression (launch-greet excluded via the named timer), exe
  rebuilt from spec and launch-checked.
- Log: `verify/phase5/phase5-log.txt`.

## FREEZE

The behavior list is **frozen** as of this report. The full animation inventory with suggested
frame counts is in [ANIMATION-INVENTORY.md](ANIMATION-INVENTORY.md): 34 animations + 5 props,
≈190–200 frames, one facing direction (mirroring is free). The two deferred hook behaviors add
exactly one animation (`typewrite`) and one prop (typewriter) when they're built, per the design
doc. Next gates, in order: the art-production-route decision, then Phase 6 (art), Phase 7
(polish, HUD default off), Phase 8 (signing/packaging).

## What felt thin

- The bark's open mouth is small at taskbar scale; with real art give the bark a visible
  muzzle-open frame and consider an optional (default-off) sound later.
- Beg and the sit fidget overlap visually at low lift — fine, since sit is rare and beg is
  user-triggered, but art should differentiate them (beg = paws up, sit = paws down).
- Greet's return-from-idle threshold (10 min) is a guess; tune by living with it.
