# Sprites and Animation (PyQt5)

> **Reality check — the POC (`biscuit.py`) uses NO spritesheets.** The shipped dog is drawn
> **procedurally** every frame with `QPainter` primitives (ellipses, rounded rects, quadratic
> `QPainterPath` curves). There are no `.png` assets, no `QPixmap`, no frame slicing, and no
> `QElapsedTimer`/`Animator` class. "Animation" is parameter-driven: phase accumulators
> (`breath_phase`, `tail_phase`, `walk_phase`) advanced each tick and fed through `math.sin`,
> plus per-state values like `bounce_val`, `stretch_factor`, and `head_bob`. A single `QTimer`
> at 33 ms (~30 Hz) drives both animation and logic; `paintEvent` redraws the whole dog from
> scratch. See §0 below for how the real code animates. The spritesheet material in §1–§5 is
> **forward-looking guidance for if/when you swap the placeholder vector art for bitmap sprites**
> — it does not describe the current code.

Spritesheet loading is fragile. A frame size off by a few pixels causes silent corruption:
frames bleed into each other, the walk cycle drifts, and you'll waste an hour blaming the
animation code when the real bug is the loader. The rule is simple: **measure the asset, never
guess.**

This file ports the spritesheet discipline from 2D game engines onto PyQt5's `QPixmap`.

---

## 0. How the POC actually animates (procedural, no assets)

The current dog is vector-drawn. The relevant real-code facts:

- **One timer, ~30 Hz.** `QTimer` at `start(33)` calls `_on_tick`, which bumps the phase
  accumulators (`breath_phase += 0.05`, `tail_phase += 0.15`, `walk_phase += 0.25`), updates
  state, rebuilds the click mask, and calls `self.update()`.
- **Full-window repaint each tick.** The POC calls `self.update()` (whole window), **not**
  `self.update(dog_rect)`. The §3 advice to repaint only the dirty rect is a valid optimization
  but is **not** what the POC does — procedural drawing of one small dog is cheap enough that the
  full-width repaint is fine here.
- **No frames, no fps per animation.** Motion comes from continuous math:
  `bh = int(18 + math.sin(self.breath_phase) * 1.5)` (breathing), `math.sin(self.walk_phase)`
  for leg swing, `math.sin(self.tail_phase)` for the wag, etc. There is no frame index to
  advance and nothing to loop.
- **Facing is a sign multiplier, not a mirrored pixmap.** `self.facing` is `-1` (left) or `+1`
  (right); every draw offset is multiplied by it (e.g. `hcx = cx + f * (bw // 2 - 2)`), so the
  dog mirrors without a second set of frames and without `QTransform`.
- **States are an enum + if/elif dispatch**, not animation clips. `_draw()` branches on
  `self.state` to call `_draw_sleeping` / `_draw_standing` / `_draw_scratch_leg` / `_draw_bone`,
  etc. (See assets-and-behaviors.md §0 for the state machine itself.)

If you keep the procedural approach, ignore §1–§2 (loaders) entirely; §3's "no `time.sleep`,
drive from a `QTimer`" rule still applies and the POC follows it.

---

## 1. STOP: inspect the spritesheet before writing loader code

Before any code, get the real numbers:

```bash
python -c "from PIL import Image; im=Image.open('assets/dog_walk.png'); print(im.size, im.mode)"
```

Then answer, on paper:

1. **Image width × height** (e.g. 512 × 64).
2. **How many frames** across and down (e.g. 8 cols × 1 row).
3. **Frame width = imageWidth / cols**, **frame height = imageHeight / rows**.
4. **Is there spacing/padding** between frames? If frames don't divide evenly, there's spacing.
5. **Verify the math:** `imageWidth = frameWidth × cols + spacing × (cols − 1)`. If it doesn't
   balance, your frame size or spacing is wrong. Fix it here, not in code.

### Hard-won rules

- **Character frames are usually square.** If you compute `frameWidth = 56`, try `frameHeight =
  56` first.
- **Each animation can have its own frame size.** A walk cycle is wider than an idle; a stretch
  is taller. Measure **every** spritesheet independently. Don't assume one frame size for all.
- **One row per animation is the easiest layout.** If art comes as one big grid, note the
  start/end frame index per animation.

### A note on art assets in this repo

There are **no PNG sprite assets in the Biscuit repo today** — the dog is entirely procedural
(see §0). The earlier reference to `Persi-walk.png` / `Persi2-sleep.png` describes a different
project's art and does not exist here. If you decide to move Biscuit from vector drawing to
bitmap sprites, you'd need multiple frames per behavior — either a horizontal strip
(`frame0 | frame1 | ...`) or separate numbered files — sized to the on-screen footprint (a
taskbar pet is tens of pixels tall, the window is only `WIN_H = 95` px). Until/unless that
happens, every behavior already "falls back" to procedural drawing, so no static-frame fallback
is needed.

---

## 2. Slicing a spritesheet into QPixmap frames

```python
from PyQt5.QtGui import QPixmap

def load_frames(path, frame_w, frame_h, count, spacing=0, row=0):
    sheet = QPixmap(path)
    if sheet.isNull():
        raise FileNotFoundError(path)  # fail loud, don't draw nothing silently
    frames = []
    y = row * (frame_h + spacing)
    for i in range(count):
        x = i * (frame_w + spacing)
        frames.append(sheet.copy(x, y, frame_w, frame_h))  # QPixmap.copy = sub-rect
    return frames
```

For pixel art, keep it crisp when scaling:

```python
from PyQt5.QtCore import Qt
scaled = frame.scaled(frame_w*scale, frame_h*scale,
                      Qt.KeepAspectRatio, Qt.FastTransformation)  # nearest-neighbor, no blur
```

Use `Qt.FastTransformation` (nearest-neighbor) for pixel art; `Qt.SmoothTransformation` blurs it.

---

## 3. Playing frames with a QTimer (never time.sleep)

`time.sleep()` blocks the UI thread and freezes the whole overlay. Drive animation from a
`QTimer` and advance frames by elapsed time so speed is frame-rate independent.

```python
from PyQt5.QtCore import QTimer, QElapsedTimer

class Animator:
    def __init__(self, repaint_cb):
        self._repaint = repaint_cb
        self.frames = []
        self.fps = 8
        self.idx = 0
        self.loop = True
        self._clock = QElapsedTimer(); self._clock.start()
        self._acc = 0.0
        self._timer = QTimer(); self._timer.timeout.connect(self._tick)
        self._timer.start(16)   # ~60 Hz tick; frame advance is governed by fps below

    def play(self, frames, fps=8, loop=True):
        self.frames, self.fps, self.loop, self.idx, self._acc = frames, fps, loop, 0, 0.0

    def _tick(self):
        dt = self._clock.restart() / 1000.0
        self._acc += dt
        step = 1.0 / self.fps
        advanced = False
        while self._acc >= step:
            self._acc -= step
            self.idx += 1
            advanced = True
            if self.idx >= len(self.frames):
                self.idx = 0 if self.loop else len(self.frames) - 1
        if advanced:
            self._repaint()   # request a repaint of the dirty region only

    @property
    def current(self):
        return self.frames[self.idx] if self.frames else None
```

Repaint only the sprite's rectangle, not the full screen-wide window:

```python
self.update(dog_rect)   # QWidget.update(QRect) marks just that region dirty
```

Full-window repaints on a taskbar-wide overlay every frame spike CPU and spin the fan.

---

## 4. Animation state machine

One animation plays at a time, chosen by the current behavior state. Some states **lock** until
their animation finishes (a one-shot like "scratch" or "yawn"), others **loop** (idle/breathing,
walk). Keep this logic in the animation/behavior layer, not the window.

```python
# pseudo-structure
STATES = {
    "sleep":  {"frames": sleep_frames,  "fps": 4,  "loop": True,  "lock": False},
    "walk":   {"frames": walk_frames,   "fps": 10, "loop": True,  "lock": False},
    "scratch":{"frames": scratch_frames,"fps": 12, "loop": False, "lock": True},
    "yawn":   {"frames": yawn_frames,   "fps": 8,  "loop": False, "lock": True},
}

def set_state(self, name):
    if self._locked and not self._anim_finished():
        return                      # don't interrupt a one-shot
    s = STATES[name]
    self.animator.play(s["frames"], s["fps"], s["loop"])
    self._locked = s["lock"]
    self._facing = self._facing    # flip handled separately
```

Facing direction: store a `facing` flag and mirror the pixmap when needed rather than keeping a
second set of frames.

```python
from PyQt5.QtGui import QTransform
mirrored = frame.transformed(QTransform().scale(-1, 1))
```

---

## 5. Verify each animation in isolation

- Load one spritesheet, play it on a loop at the resting position, and watch a full cycle.
  Frames should flow cleanly with no bleeding or jump. Bleeding = wrong frame size or spacing.
- For one-shots (scratch, yawn), trigger once and confirm it plays through and returns to idle.
- Confirm the sprite scales crisply (no blur) at its on-screen size.
