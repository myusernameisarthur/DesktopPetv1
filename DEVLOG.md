# Biscuit — Development Log

This document captures every decision made during the project, in order. It's written so a new developer (or a new AI instance) can understand not just *what* was built, but *why* each choice was made.

---

## About the creator

**Arthur** is the sole creator of this project. He had no prior Python or Qt experience before this session. He came in with a clear product vision — a Windows desktop pet dachshund — and directed all aesthetic and behavioral decisions. Technical implementation was handled by Claude (Anthropic's AI assistant) in a back-and-forth session.

Arthur's email: roussilhevalentine@gmail.com  
GitHub: myusernameisarthur

---

## Session overview

The entire project was built in one extended Claude conversation. Arthur gave high-level requirements; Claude wrote code; Arthur tested the running exe and reported bugs or new ideas. This is a record of what was decided and why at each stage.

---

## Step 1 — Initial requirements and stack choice

**Arthur's brief:**
- Windows desktop pet
- Transparent always-on-top overlay
- Sausage dog on the taskbar
- No window chrome, no UI — just the dog
- Bottom-right corner, above the clock
- Placeholder art only — real sprites come later
- Behaviors: sleeping, walking, cursor awareness, click reactions, right-click menu
- Package as a single `.exe`

**Stack decision: Python + PyQt5 + PyInstaller**

- Python: Arthur didn't specify a language; Python was chosen for quick iteration and rich Qt bindings.
- PyQt5 over PySide6: Both are Qt Python bindings. PyQt5 was already pip-installable with no issues.
- PyInstaller `--onefile --windowed`: bundles Python runtime + dependencies into one `.exe` with no console window.

**Window architecture decision: full-width static window**

Two approaches were considered:
1. Small window that moves with the dog (repositioned every frame during walks)
2. Full-width window that starts at x=0, dog drawn at changing x coordinates inside it

Option 2 was chosen because option 1 would require `setGeometry` calls at 30 fps during walks, which causes visible flicker on Windows.

The tradeoff: a full-screen-width window means `setMask(QRegion)` must include the dog's bounding box (updated every tick) plus the corner decorations. This is a lightweight operation.

**Click-through implementation:**

`Qt.WA_TranslucentBackground` makes the window glass. But the widget still captures events for its entire geometry including transparent areas. `setMask(QRegion)` restricts which pixels capture mouse events — areas outside the mask are fully click-through. The mask is rebuilt each tick to track the dog's position.

**Always-on-top above taskbar:**

`Qt.WindowStaysOnTopHint` isn't always sufficient to stay above the Windows 11 taskbar (which is itself a topmost window). The fix: call `SetWindowPos(hwnd, HWND_TOPMOST, ...)` directly via `ctypes.WinDLL("user32")` after show, and re-assert every 6 seconds (every 180 ticks at 30 fps) as insurance.

**Hide from taskbar:**

`Qt.Tool` flag hides the window from the taskbar and alt-tab switcher without making it a child window.

---

## Step 2 — Drawing the dog

All drawing is done with `QPainter` in `paintEvent`. The coordinate origin for drawing is always `(int(self.dog_sx), DOG_BASE)` where `dog_sx` is the dog's current x in screen/window coordinates and `DOG_BASE` is the fixed y baseline (the "floor").

**Sleeping pose:**
- Body: `drawEllipse` — wide horizontal ellipse (~68 × 18 px)
- Head: `drawEllipse` — circle (r=13) at the facing end of the body
- Ear: `drawEllipse` — slightly darker ellipse hanging below the head
- Eye: `drawArc` — a closed arc (sleeping)
- Nose: `drawEllipse` — small dark oval
- Legs: four `drawRoundedRect` calls — small nubs below body
- Tail: `QPainterPath.quadTo` — a curved line at the back

**Standing/walking pose:**
- Same structure but body is more upright, legs are full length (~17 px), tail wags via `sin(tail_phase)`
- `walking=True` adds a leg-swing animation: `sin(walk_phase) * 5` offset applied to alternating pairs of legs

**Facing direction:** tracked as `self.facing` = `-1` (left) or `1` (right). All drawing offsets are multiplied by `f` so the dog faces correctly in both directions.

**Animation phases:** `breath_phase`, `tail_phase`, `walk_phase` are float accumulators incremented each tick. Each drives a `sin()` call for smooth oscillation.

**`CompositionMode_Clear` before each frame:** the entire window rect is cleared to transparent before drawing. This is what makes the background invisible — without this, previous frames would accumulate.

---

## Step 3 — Taskbar positioning (multiple iterations)

This was the hardest technical problem. The dog needed to sit exactly on the taskbar surface, not float above it.

**Bug 1: `SHAppBarMessage` returns physical pixels, `setGeometry` takes logical pixels.**

The first implementation used the Windows Shell API (`SHAppBarMessage` with `ABM_GETTASKBARPOS`) to detect taskbar position. On DPI-scaled displays (125%, 150% — common on modern Windows laptops and monitors), the shell API returns raw physical pixel coordinates while Qt's `setGeometry` and all painting operate in logical (DPI-independent) pixels. This misalignment placed the window at the wrong vertical position.

Fix: replaced `get_taskbar_rect()` entirely with `QScreen.availableGeometry()`:

```python
screen = QApplication.primaryScreen()
ag = screen.availableGeometry()  # excludes taskbar, in logical px
tb_top = ag.bottom() + 1         # first row of taskbar
```

This always matches `setGeometry`'s coordinate space, regardless of DPI.

**Bug 2: off-by-one in Qt's drawing model.**

Qt's `drawEllipse(x, y, w, h)` paints rows `y` through `y+h-1` (the last painted row is `y+h-1`, not `y+h`). The original `DOG_BASE = WIN_H - 1` caused all shapes to end at `WIN_H - 2`, one pixel above the taskbar edge.

Fix: `DOG_BASE = WIN_H` (exclusive bottom). Last painted row = `WIN_H - 1` = window's last pixel row = `tb_top`.

**Final window placement formula:**

```python
wy = tb_top - WIN_H + 1
# proof: wy + WIN_H - 1 = tb_top  ✓
```

The window's last pixel row (row `WIN_H - 1`) lands exactly on `tb_top` in screen coordinates. `DOG_BASE = WIN_H` means shapes drawn at `y = DOG_BASE - h` have their last pixel at `WIN_H - 1 = tb_top`. Dog and decorations all sit on the same floor.

---

## Step 4 — Corner home and objects

Arthur specified that the bottom-right area (above the system tray clock) is the dog's permanent home. Three objects live there:

- **Bed** — wide oval cushion. Started as tan/brown. Changed to white (`QColor(250, 250, 250)`) after testing revealed the brown dog was invisible against a brown cushion.
- **Water bowl** — small ellipse. Blue (`QColor(148, 198, 222)`) when full, grey when empty.
- **Ball** — red circle with a lighter highlight spot. Used `QColor(215, 70, 45)`.

**Corner positions (relative to `tb_right`):**
```
bed_cx  = tb_right - 160
bowl_cx = tb_right - 95
ball_cx = tb_right - 65
```

These values were chosen to fit within the open taskbar space to the left of the clock/system tray area, which typically occupies the rightmost ~60px.

**Dog always returns to bed to sleep:** Arthur's requirement. Walk cycle changed from "stop anywhere → sleep" to a two-phase walk: roam phase → `returning = True` → walk toward `bed_cx` → `SLEEPING`. The `_walk_toward(dest)` helper drives all targeted walks.

---

## Step 5 — Sleep/walk timing

**Original timing (too fidgety):** a QTimer fired every 4.5 s with 35% chance of walking → average walk every ~13 seconds. The dog felt like a broken toy.

**New timing (feels like a real pet):**
- Single-shot `_sleep_timer`: fires after a random **4–8 minutes** of sleep
- Walk duration: **30–90 seconds** (in frames at 30 fps = 900–2700 frames)
- ~85% of time asleep

Implementation: `QTimer.setSingleShot(True)`. Re-armed with `_arm_sleep_timer()` every time the dog settles onto the bed from any activity. The timer fires `_start_walk()` which checks readiness and starts the behavior.

---

## Step 6 — Fetch mechanic

**Flow:**
1. User clicks ball (only when at corner and not already fetching)
2. `_throw_ball()`: ball_x set to `random.randint(walk_min, bed_cx - 70)` — teleports instantly ("no animation yet" per Arthur)
3. State → `FETCHING`: dog walks toward `ball_x`
4. On arrival: `ball_visible = False` (ball disappears = dog picks it up), 15-frame pause
5. State → `RETURNING_BALL`: dog walks toward `bed_cx`
6. On arrival: `ball_x = ball_cx`, `ball_visible = True` (ball reappears at corner), dog sleeps

**Carrying visual:** a small red circle drawn at `dog_sx + facing * 28` near head height while in `RETURNING_BALL`.

**Auto-recovery:** `_start_walk()` checks `if ball_visible and abs(ball_x - ball_cx) > 20` first — if the ball was thrown but the dog was distracted before fetching, the dog will go get it before doing a normal walk.

---

## Step 7 — Stretch and water reminders

Arthur wanted the dog to remind him to stretch and drink water — a productivity/wellness feature.

**Pending-flag pattern (used for both):**

Repeating QTimers fire every 30 min (stretch) or 60 min (water). They set `stretch_pending = True` / `water_pending = True`. `_check_pending()` is called at the top of `_update_state()` every tick. If the dog isn't in a specialized task, it consumes the flag immediately. If it is busy, the flag waits until the current task completes.

This avoids nested interruptions while guaranteeing the reminder always fires eventually.

**Stretch animation:** body widens via `bw = 68 + int(stretch_factor * 25)`. The nose ellipse grows in height (yawn) when `stretch_factor > 0.4`. `stretch_factor = sin(π * frame / 90)` for a smooth 0→1→0 envelope over 3 seconds.

**Drinking animation:** dog walks to `bowl_cx - 20` (so head reaches the bowl), faces right, head bobs with `max(0, sin(frame * 0.25)) * 10` px downward displacement for 80 frames. If bowl is empty: 30 frames of looking. Bowl state: `self.bowl_full` flips to `False` after drinking.

---

## Step 8 — Idle behavior variety

After timing was fixed, the dog felt repetitive. Arthur asked for variety in idle behaviors. Three new behaviors were added alongside normal walks:

**Scratch (3–4 s):**
- Dog stays in sleeping pose at bed
- Body shakes ±1.5 px per axis using two different sin frequencies
- A "kicking leg" is drawn as a line from the back hip toward the ear using:
  ```python
  hip_x = cx - f * 14           # opposite side from head
  tip_x = hip_x + f * extent    # swings toward head
  ```
  `extent = max(0, sin(frame * 0.85)) * 22` — unidirectional kick

**Chew bone (8–10 s):**
- Dog stands at bed
- A bone shape drawn near the mouth: `drawRoundedRect` shaft + two `drawEllipse` knob ends
- Head bobs `max(0, sin(frame * 0.30)) * 5` px downward while chewing
- Bone disappears when done; dog goes straight to `SLEEPING`

**Sniff walk:**
- Dog walks at 0.75 px/frame (half normal speed) toward a random point 100–400 px to the left
- `head_bob = 8` while walking, `10` while paused — nose held close to ground
- Every 20–30 px traveled: `task_phase = 1`, pauses for 12–18 frames (~0.5 s)
- After each pause: `sniff_next_pause` advances further along the route
- On arrival at destination: `TASK_RETURN` walks dog home

**Weighting:** `random.choice(('walk', 'scratch', 'chew', 'sniff'))` — equal 25% chance.

---

## Step 9 — State machine (complete)

```
SLEEPING
  ├─(sleep timer fires)──► _start_walk() picks one of:
  │    ├─ WALKING → (state_frames expire) → returning=True → SLEEPING
  │    ├─ SCRATCHING → (state_frames expire) → SLEEPING
  │    ├─ CHEWING → (state_frames expire) → SLEEPING
  │    └─ SNIFF_WALK → (reach dest) → TASK_RETURN → SLEEPING
  ├─(ball click) ──► FETCHING → RETURNING_BALL → SLEEPING
  ├─(cursor enters 150px) ──► ALERT → (cursor leaves + 3s) ──► SLEEPING
  └─(left click dog) ──► EXCITED (2.5s) ──► SLEEPING

Any non-task state:
  ├─(stretch_pending) ──► STRETCHING (3s) → TASK_RETURN → SLEEPING
  └─(water_pending) ──► DRINKING → TASK_RETURN → SLEEPING

All paths to SLEEPING call _arm_sleep_timer()
```

**`_walk_toward(dest)` helper:** used by all targeted walks. Moves `dog_sx` 1.5 px per call toward `dest`, sets `facing`, returns `True` when arrived (within 2 px).

---

## Step 10 — Test menu

All behaviors that take minutes or hours to fire naturally are exposed in the right-click menu under a "Test" section:

- Test: stretch
- Test: water reminder  
- Test: fetch
- Test: scratch
- Test: chew bone
- Test: sniff walk

Each method resets task state (`task_phase`, `task_frames`, `stretch_factor`), stops the sleep timer, and sets `state` directly. Arthur said to keep these permanently — they're useful for development and debugging.

---

## Technical constants

```python
WIN_H   = 95         # window height in logical pixels
DOG_BASE = WIN_H     # exclusive bottom of all bounding rects (= taskbar top)
WALK_SPEED = 1.5     # px per frame (normal walk)
SNIFF_SPEED = 0.75   # px per frame (sniff walk)
ANIM_FPS = 30        # ~33ms timer
SLEEP_MIN = 4 * 60   # seconds
SLEEP_MAX = 8 * 60   # seconds
WALK_MIN  = 30       # seconds
WALK_MAX  = 90       # seconds
STRETCH_INTERVAL = 30 * 60  # seconds
WATER_INTERVAL   = 60 * 60  # seconds
```

---

## Known issues / future considerations

- **Sprites:** all drawing is QPainter geometry. Replace with `QPixmap` sprites when art is ready. The state machine and behavior logic are fully independent of the renderer — swapping in sprites should only require changing `_draw_sleeping`, `_draw_standing`, and the new behavior draw methods.
- **DPI on secondary monitors:** `QScreen.availableGeometry()` queries the primary screen. If the taskbar is on a secondary monitor, positioning will be wrong.
- **`_arm_sleep_timer` not called after `EXCITED` in some edge cases:** mitigated by calling it in the EXCITED→SLEEPING transition, but if `_start_walk` is called while the dog is in EXCITED, it retries in 30 s.
- **Ball stuck on taskbar if dog is interrupted mid-fetch:** handled by `_start_walk` auto-fetch check, but if app is restarted mid-fetch, ball_x is not persisted (no config file yet).
