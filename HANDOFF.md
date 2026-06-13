# Biscuit — Handoff Document

> ## ⚠️ Phase 1–6 addendum — read this first (added 2026-06-12)
>
> The body of this file describes the **Phase 0 POC** and is kept for history. It is
> now out of date in several ways: there are **18 states, not 12**; the code is **no
> longer one file**; settings **are** persisted; and the dog now renders from **real
> pixel-art sprites**, not only QPainter geometry.
>
> **Current source of truth, in order:**
> - `docs/persi-roadmap.md` — the full plan and phase status (Phase 6 code = done).
> - `docs/PHASE-1-REPORT.md` … `PHASE-6-REPORT.md` — what each phase built and why.
> - `OUTPUTS/persi-art/NEXT-STEPS.md` — the live work queue.
> - `OUTPUTS/persi-art/OPEN-ITEMS.md` — which art is final vs placeholder (the ship gate).
> - `docs/ANIMATION-INVENTORY.md` — the frozen animation list.
>
> **Modules now (all imported by `biscuit.py`):**
> `fidgets.py` (idle micro-behavior engine), `gestures.py` (roll-over circle recognizer),
> `settings.py` (persisted `%APPDATA%\Persi\settings.json`), `sprites.py` (manifest-driven
> sprite renderer + kit discovery), `debug_hud.py` (dev HUD). Art pipeline:
> `tools/art/pack.py` **generates** `assets/manifest.json` from its timing table — never
> hand-edit the manifest; `tools/art/artlib.py` + `batch0.py` build the frames.
>
> **Changed invariants since the POC:**
> - `WIN_H = 190` now (was 95), still with `DOG_BASE = WIN_H`. The window grew to fit the
>   dog at the 200% size toggle; everything is bottom-anchored so the extra height is
>   invisible masked area. `wy = tb_top - WIN_H + 1` still holds.
> - The renderer is selected by `art.kit` ("procedural" = the geometry below, "pixel" =
>   sprites, plus drop-in `assets/kits/<name>/`). `art.scale` (0.75–2.0) scales the dog
>   and props via a feet-anchored QPainter transform; the mask, hit-tests and corner
>   layout all scale with it.
> - Verify with **`python tools/verify_phase6.py`** (must pass) and
>   **`python tools/smoke_phase6.py`** (renders real states + asserts integration logic).
>
> The Phase-0 detail below is still correct about the window/click-through/topmost
> plumbing, which is unchanged.

---

**For:** a new Claude instance (or any developer) picking up this project  
**Context:** this was built entirely in one session. Arthur is new to Python/GitHub. Everything is in one file. The codebase is clean and intentionally simple.

---

## Who is Arthur

Arthur is the creator and only user of this app. He has no prior Python or Qt experience. He is product-minded and visual — he directs *what* the dog does and *how it feels*, not the implementation details. He works by running the app, observing behavior, and reporting back. He is decisive and moves fast.

**His email:** roussilhevalentine@gmail.com  
**GitHub:** myusernameisarthur

**How to work with Arthur:**
- Implement completely, test, and hand him a working exe before asking questions
- He says "two changes only, don't touch anything else" — take that literally
- When he says something "feels wrong" (floating, too fast, too fidgety), he's right — diagnose from first principles
- He keeps test triggers in the menu permanently — don't remove them

---

## Repo layout

```
biscuit.py     — entire app, ~900 lines
Biscuit.spec   — PyInstaller spec (auto-generated, keep it)
README.md      — user-facing overview
DEVLOG.md      — full decision history (read this first)
HANDOFF.md     — this file
.gitignore     — excludes build/, dist/, __pycache__
```

There is no config file, no database, no tests, no CI. One Python file, one exe.

---

## Architecture in one paragraph

A single `Biscuit(QWidget)` with a full-screen-width transparent window fixed at `(0, tb_top - WIN_H + 1)`. The dog's x-coordinate (`dog_sx`) is tracked in screen space; since the window starts at x=0, window-local x == screen x everywhere. A `setMask(QRegion)` updated every tick restricts click capture to the dog's bounding box + corner decorations. All drawing uses `QPainter` with `CompositionMode_Clear` before each frame. A 33ms QTimer drives animation; a single-shot `_sleep_timer` drives behavior scheduling.

---

## Key invariants — do not break these

| Invariant | Why |
|---|---|
| `DOG_BASE = WIN_H` | Last painted pixel = `WIN_H - 1` = taskbar top. If you change `WIN_H`, `DOG_BASE` stays `= WIN_H`. |
| `wy = tb_top - WIN_H + 1` | Ensures `wy + WIN_H - 1 == tb_top`. **Never use SHAppBarMessage** — it returns physical pixels, `setGeometry` wants logical. |
| `ground = WIN_H` in `_draw_corner` | Same baseline as `DOG_BASE`. Don't change to `DOG_BASE - 1` or anything else. |
| `_arm_sleep_timer()` called on every `→ SLEEPING` transition | If you add a new path to SLEEPING, call it. The dog sleeps forever if you forget. |
| `_check_pending()` at top of `_update_state()` | Reminder flags stay set until consumed. Don't move this. |

---

## State machine (complete)

```python
class State(Enum):
    SLEEPING = 0        # on bed, breathing, zzz bubbles
    ALERT = 1           # cursor within 150px, tail wags, faces cursor
    WALKING = 2         # normal roam, returns to bed
    EXCITED = 3         # left-click reaction, bounce + tongue, 2.5s
    FETCHING = 4        # walking to thrown ball
    RETURNING_BALL = 5  # carrying ball home
    STRETCHING = 6      # 3s stretch animation, then TASK_RETURN
    DRINKING = 7        # walk to bowl + drink animation
    TASK_RETURN = 8     # generic "walk to bed then SLEEP" state
    SCRATCHING = 9      # 3-4s idle: sleeping pose + kicking leg
    CHEWING = 10        # 8-10s idle: standing + bone + head bob
    SNIFF_WALK = 11     # slow walk with nose down, pausing to sniff
```

**Transitions that arm the sleep timer:**  
`WALKING(returning)→SLEEPING`, `EXCITED→SLEEPING`, `RETURNING_BALL→SLEEPING`, `STRETCHING→SLEEPING`, `TASK_RETURN→SLEEPING`, `SCRATCHING→SLEEPING`, `CHEWING→SLEEPING`

**Pending-flag pattern (reminders):**  
`_on_stretch_timer()` sets `stretch_pending = True`. `_check_pending()` at top of `_update_state()` consumes it and starts `STRETCHING` if not already in a task. Same for `water_pending`. This ensures reminders always fire eventually without nested interruptions.

---

## Critical methods

| Method | What it does |
|---|---|
| `_place_window()` | Sets window geometry once at startup. Never called again. |
| `_update_mask()` | Rebuilds click/visibility region every tick. Covers dog box + corner decorations + stray ball. |
| `_walk_toward(dest)` | Moves `dog_sx` 1.5px/tick toward `dest`. Sets `facing`. Returns `True` on arrival. Used by all targeted walks. |
| `_check_pending()` | Consumes `stretch_pending` / `water_pending` if not in a task. Called first in `_update_state()`. |
| `_arm_sleep_timer()` | Starts single-shot timer for 4–8 random minutes. Call on every → SLEEPING transition. |
| `_start_walk()` | Called by sleep timer. Checks for stray ball first. Picks one of 4 behaviors (25% each). |
| `_assert_topmost()` | WinAPI `SetWindowPos(HWND_TOPMOST)`. Called at startup + every 180 ticks. |

---

## Drawing methods

| Method | State it renders |
|---|---|
| `_draw_sleeping(p, cx, base, f, ...)` | `SLEEPING`, `STRETCHING`, `SCRATCHING` |
| `_draw_standing(p, cx, base, f, ..., head_bob=0)` | everything else |
| `_draw_corner(p)` | always — bed, bowl, ball |
| `_draw_scratch_leg(p, cx, base, f, DARK)` | overlay on top of `_draw_sleeping` during `SCRATCHING` |
| `_draw_bone(p, cx, base, f, head_bob)` | overlay on top of `_draw_standing` during `CHEWING` |

`_draw_sleeping` reads `self.stretch_factor` to widen the body and open the yawn. It has no other parameters for this — don't add them, just read from `self`.

`_draw_standing` has `head_bob=0` param. Positive values lower the head (used for `DRINKING` and `SNIFF_WALK`).

---

## Corner positions

All three corner objects are at fixed screen x positions derived from `tb_right` (the right edge of the taskbar):

```python
bed_cx  = tb_right - 160   # dog sleeps here
bowl_cx = tb_right - 95    # water bowl
ball_cx = tb_right - 65    # ball home position
```

These values assume the system tray clock takes ~60 px from the right edge. They may need adjustment for non-standard taskbar configurations.

---

## Timing constants

```python
# Sleep timer: 4–8 min (single-shot, re-armed on every → SLEEPING)
ms = random.randint(4 * 60 * 1000, 8 * 60 * 1000)

# Walk duration: 30–90 s at 30fps
state_frames = random.randint(30 * 30, 90 * 30)

# Stretch duration: 3 s = 90 frames
# Scratch duration: 3–4 s = 90–120 frames
# Chew duration: 8–10 s = 240–300 frames
# Drink (full bowl): 80 frames. Drink (empty bowl): 30 frames (just looking)

# Reminder timers (repeating, not single-shot)
_stretch_timer: 30 * 60 * 1000 ms
_water_timer:   60 * 60 * 1000 ms
```

---

## What's next (Arthur's intentions)

Arthur wants to eventually replace the QPainter placeholder art with real sprite illustrations of a dachshund. The state machine and behavior logic are completely independent of the renderer — the only methods that need to change are `_draw_sleeping`, `_draw_standing`, `_draw_scratch_leg`, `_draw_bone`, and `_draw_corner`. Everything else stays.

**Short-term backlog (likely next session topics):**
- More idle behaviors (dream twitching, tail chase)
- Settings persistence (save reminder on/off state to a JSON file)
- Sound effects (optional, default off)
- Configurable reminder intervals via a settings dialog

**Do not:**
- Add complexity to the state machine without Arthur explicitly asking
- Change timing without Arthur testing it
- Remove test triggers from the menu
- Use `SHAppBarMessage` for taskbar detection

---

## Build instructions

```bash
# Dev
pip install PyQt5
python biscuit.py

# Package
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name Biscuit biscuit.py
# Output: dist/Biscuit.exe
```

Python 3.11, Windows only. No other dependencies.
