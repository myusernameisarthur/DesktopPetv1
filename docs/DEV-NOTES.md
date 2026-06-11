# DEV-NOTES — architecture as found (Step 0, 2026-06-11)

How the app actually works at the start of Phase 1, written after reading the roadmap, the
behavior map, the `transparent-desktop-app` skill (SKILL.md + all four references),
RECONCILIATION-NOTES.md, `biscuit.py`, `debug_hud.py`, and `Biscuit.spec`. Where the skill and
the code disagree, the code wins (already reconciled in the skill text).

---

## Shape of the app

Everything lives in one QWidget subclass, `Biscuit` (biscuit.py), plus a self-contained dev HUD
(`debug_hud.py`). No assets, no manifest — the dog is **drawn procedurally** with QPainter
primitives; motion is `math.sin` over phase accumulators. One `QTimer` at 33 ms (~30 Hz) drives
animation, logic, mask, repaint, and HUD refresh.

- **Window:** frameless, translucent, always-on-top, `Qt.Tool`, `NoDropShadowWindowHint`,
  `WA_ShowWithoutActivating`. A full-screen-width strip of height `WIN_H = 95` placed so its last
  pixel row lands on the taskbar's top edge (`get_taskbar_rect()` from
  `QScreen.availableGeometry()`, all in Qt logical pixels — deliberately no high-DPI attribute).
  Window x starts at 0, so window-local x == screen x everywhere.
- **Click-through:** a per-frame `setMask(QRegion)` (`_update_mask`) — union of the dog's
  current footprint rect (curled 120×38 for SLEEPING/STRETCHING/SCRATCHING, standing 104×75
  otherwise), the decor rect (bed+bowl+ball corner), and the thrown ball's rect. Rebuilt every
  tick. Everything outside the mask is not part of the window, so clicks pass through.
  **No Win32 input-transparency toggle in the main window.**
- **Topmost:** `_assert_topmost()` (SetWindowPos HWND_TOPMOST, SWP_NOACTIVATE) at startup and
  every 180 ticks (~6 s).

## The state machine

A single `State` enum (12 states) dispatched by an `if/elif` chain in `_update_state()`; each
state has an `_update_<x>()` helper that mutates `self` and flips `self.state` when done. No
Behavior/Scheduler objects. Default state is `SLEEPING` on the bed; almost everything ends with
`state = SLEEPING; facing = -1; _arm_sleep_timer()`.

| State | ANIM label | Driven by |
|-------|-----------|-----------|
| SLEEPING | `breathing` | breath_phase swell, Zzz bubbles |
| ALERT | `alert-stand` | standing pose, fast tail wag, no steps |
| WALKING | `trot` | roam between walk_min and bed; state_frames countdown |
| EXCITED | `bounce` | bounce_val + tongue + wag; 75 frames |
| FETCHING | `trot` | walk to thrown ball, 15-frame pickup |
| RETURNING_BALL | `trot-carry` | walk home with ball at mouth |
| STRETCHING | `stretch` | lying pose + stretch_factor + yawn; 90 frames |
| DRINKING | `drink` | walk to bowl (phase 0) then head-bob drink (phase 1) |
| TASK_RETURN | `trot` | walk home after a task |
| SCRATCHING | `scratch` | lying pose + jitter + kicking back leg |
| CHEWING | `chew` | standing + head-bob + bone |
| SNIFF_WALK | `sniff` | 0.75 px/tick walk, nose down, random sniff-pauses |

`ANIMATION` (biscuit.py top) is the single source of truth mapping state → animation label;
`current_anim()` reads it and the HUD displays it. Several states share `trot` — that's the
Phase 3 target.

**Triggers:**
- Ambient: `_arm_sleep_timer()` — single-shot 4–8 min; on fire `_start_walk()` picks
  `random.choice(('walk','scratch','chew','sniff'))` with equal weight (fetches a stranded ball
  first). Not-ready → retry in 30 s.
- Timed: stretch every 30 min, water every 60 min → `*_pending` flags consumed by
  `_check_pending()` only when no task state is active (this is what makes one-shots
  non-interruptible).
- Interactive: cursor within 150 px → face cursor, SLEEPING→ALERT, settle back after 90 ticks;
  left-click dog → EXCITED; click ball at corner → throw/FETCHING; click bowl → refill.
- One-shots use frame counters (`task_frames` vs `state_frames`/fixed durations), not lock flags.

## Drawing

`paintEvent` clears to transparent then `_draw(p)`: corner objects first, then the dog by state.
Two base poses: `_draw_sleeping` (body ellipse w/ breathing height, tail path, head, ear, closed
eye arc, nose/yawn, 4 tucked legs) and `_draw_standing` (4 legs w/ sin leg-swing when walking,
body, tail w/ wag, head w/ optional head_bob, ear, open eye, nose, optional tongue). Extras:
`_draw_scratch_leg`, `_draw_bone`, carried ball, Zzz bubbles. **Facing is a sign multiplier
`f = ±1`** applied to every horizontal offset — no mirrored assets.

Key drawing inputs: `breath_phase` (+0.05/tick), `tail_phase` (+0.15), `walk_phase` (+0.25),
`bounce_val`, `stretch_factor`, `head_bob`, `task_frames`.

## Right-click menu (`_show_menu`)

Flat list: Pause animations, Launch at startup, Stretch reminders, Water reminders (all
checkable, in-memory except startup) · separator · "Test" section: stretch, water reminder,
fetch, scratch, chew bone, sniff walk (each force-fires its state, stopping the sleep timer) ·
separator · Debug HUD toggle · Quit.

## Persistence

Only the **`HKCU\...\CurrentVersion\Run` registry value "Biscuit"** (launch at startup), written
with the correct `sys.frozen`-aware command line. Menu toggles reset every launch. No
%APPDATA% settings file yet (that's Phase 2).

## Debug HUD (`debug_hud.py`)

A separate small frameless window, fully click-through at two levels (`Qt.WindowTransparentForInput`
plus Win32 `WS_EX_TRANSPARENT|WS_EX_LAYERED` in showEvent), so it can never eat input. No timer
of its own — `Biscuit._on_tick` calls `hud.refresh(self)` each frame. It reads live attributes
(state, `current_anim()`, phase helpers, facing, QTimer.remainingTime for next wander/stretch/
water) and tracks time-in-state itself. It follows the dog horizontally, clamped on-screen.
Layout is font-metrics-driven; **the fixed height is sized to the line count** (currently 6
lines — adding a line means updating the `line_h * 5` term and the widest-value probe).
All hooks in biscuit.py sit in `# === DEBUG HUD ===` blocks; delete those + the file to remove.

## Build

`Biscuit.spec`: one-file windowed exe, `datas=[]` (nothing to bundle), upx, no icon.
Build: `python -m PyInstaller --noconfirm Biscuit.spec` (pyinstaller 6.20, Python 3.11.9,
output `dist/Biscuit.exe`). Iterate with `python biscuit.py`; rebuild only at phase boundaries.

## Invariants to protect (the things that break this kind of app)

1. The mask must always cover exactly the dog + objects — new visuals (props, fidget deltas)
   must stay inside the masked rects or extend the mask.
2. New overlay windows must be input-transparent like the HUD, or they steal desktop clicks.
3. One behavior at a time; never interrupt a running one-shot; everything returns to SLEEPING
   and re-arms the sleep timer.
4. Stay in Qt logical pixels; don't introduce high-DPI scaling without redoing taskbar math.
5. `ANIMATION` map and the HUD must stay truthful as states/animations are added.

## Plan from here

- Phase 1 (`feature/phase-1-idle-engine`): `fidgets.py` engine (irregular 4–12 s gaps, weights,
  no-repeat memory, per-fidget cooldown, one at a time, cancel on state change, rate-mult hook);
  lying catalog (ear-flick, nose-twitch, tail-twitch, sigh, dream-kick, eye-crack, resettle,
  scratch-as-rare-fidget); standing catalog in ALERT (blink, ear-swivel, weight-shift, head-tilt,
  look-around, tail-wag-burst, shake-off, bone-chew, sit-as-rare-fidget); ALERT re-signature
  (ears up, calmer default tail, slightly busier fidget rate); HUD FIDGET line.
- Phase 2 (`feature/phase-2-settings`): JSON settings in `%APPDATA%\Persi\settings.json`, grouped
  checkable menu, every behavior gated on its switch, Test bypasses switches.
- Phase 3 (`feature/phase-3-gaits`): gait parameter table (brisk trot / plod / scamper /
  sniff-walk), states routed to gaits, ANIMATION labels updated.
- STOP before Phase 4 (global keyboard / window hooks) for explicit go-ahead.
