# Phase 2 Report — Settings control board

Date: 2026-06-11 · Branch: `feature/phase-2-settings` · Tag on merge: `phase-2-complete`

## What was built

**`settings.py`** — a persisted settings store: JSON at `%APPDATA%\Persi\settings.json`,
written atomically (tmp + replace), created with defaults on first run, healed to defaults if
the file is corrupt, unknown/wrong-typed keys ignored. One switch per behavior; adding a new
behavior later is one `DEFAULTS` row plus one menu line.

| Group | Switch (default) |
|---|---|
| Idle | fidgets_lying (on), fidgets_standing (on), wander_walk (on), scratch (on), chew (on), sniff_walk (on) |
| Timed | stretch_reminders (on), water_reminders (on) |
| Interactive | cursor_alert (on), excited_on_click (on), fetch_ball (on) |
| Debug | hud (on — flips to off in Phase 7) |

Deliberate exceptions: **Launch at startup** stays in the registry (Windows itself reads the
`HKCU\...\Run` key, so it can't live in JSON); **Pause animations** stays session-only.

**Every behavior now reads its switch at fire time:**
- `_start_walk` picks only among the enabled ambient behaviors; all off → keeps sleeping.
- Stretch/water pendings are consumed but only fire if their switch is on.
- Cursor proximity (ALERT + facing) is skipped entirely when off, settling any live alert.
- Dog-click → EXCITED and ball-click → FETCH are gated in `mousePressEvent`.
- The fidget engine receives no pose (so it stays silent) when the matching pose switch is off.
- **The Test menu bypasses all switches** — it sets states directly, unchanged.

**Menu reorganized** into grouped checkable submenus — Idle / Timed / Interactive — between the
top-level controls (Pause, Launch at startup) and the existing flat Test section + Debug HUD
toggle + Quit. Toggle changes save immediately. Per the decision default, this stays in the
right-click menu until the toggle count nears ~15 (Phases 4–5 will add Command / Reactive /
Modes groups).

## Verification (tools/verify_phase2.py — 15 automated checks on the real app, all PASS)

Settings isolated to a temp `%APPDATA%` during the run, so real user settings were untouched.

- Fresh start loads defaults; a toggle persists to disk and is read back by a fresh `Settings`
  instance (restart simulation); a corrupt file falls back to defaults.
- Ambient all off → dog stays asleep and the sleep timer re-arms; only-chew-on → picks chew.
- Stretch and water reminders honor their switches (off: pending consumed, no state change).
- Cursor alert off: cursor parked next to the dog for 1.2 s produces no ALERT; on: ALERT.
- Click-excited and ball-fetch honored at the real `mousePressEvent` path.
- Lying fidgets off: zero fidgets in 4 s at 30× rate; back on: they fire again.
- `Test: scratch` force-fires SCRATCHING while `idle.scratch` is off.
- Menu structure: exactly the three behavior submenus (6/2/3 actions), all checkable, checked
  state mirrors the store live, all 6 Test entries intact.
- Exe rebuilt from the spec; frozen run creates `%APPDATA%\Persi\settings.json` on first launch.
- Log: `verify/phase2/phase2-log.txt`; menu screenshot: `verify/phase2/menu-grouped.png`.

Click-through and windowing untouched this phase (no new windows, no mask changes); Phase 1's
`WindowFromPoint` probes still apply.

## What felt thin

- `QMenu.addSection("Behaviors")` renders as a plain separator on Windows — cosmetic only.
- No "Test: excited" entry exists (click the dog instead); worth adding when Phase 5 grows the
  Test section.
- The state→animation table is unchanged this phase (settings don't add states).
