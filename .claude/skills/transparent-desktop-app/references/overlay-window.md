# Overlay Window: transparent, always-on-top, click-through-except-sprite

The window is the foundation and the easiest thing to get subtly wrong. Goal: a frameless,
fully transparent window that sits on the taskbar, stays above everything, never appears in the
taskbar button list, and passes mouse input through to the desktop **except** when the cursor
is over an interactive sprite or object.

> **This file documents what `biscuit.py` (the working POC) actually does.** A prior version of
> this skill recommended a Win32 input-transparency toggle and high-DPI scaling. The shipped
> code uses neither — it uses a per-frame **window mask** and stays in Qt logical pixels, and it
> works. Where this file and the old guidance differ, the code is the source of truth.

---

## 1. Base window flags (as used in `Biscuit.__init__`)

```python
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget

class Biscuit(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint        # no title bar / border
            | Qt.WindowStaysOnTopHint     # always on top
            | Qt.Tool                     # keep OUT of taskbar buttons + alt-tab
            | Qt.NoDropShadowWindowHint   # no shadow box around the translucent window
        )
        self.setAttribute(Qt.WA_TranslucentBackground)   # transparent, not black
        self.setAttribute(Qt.WA_ShowWithoutActivating)   # don't steal focus on show
```

Notes from the real code:
- `Qt.Tool` is the flag people miss. Without it the transparent overlay shows up as its own
  taskbar button. With it, the overlay is invisible to the taskbar and alt-tab.
- `Qt.NoDropShadowWindowHint` is included so Windows doesn't draw a shadow rectangle around the
  otherwise-invisible window.
- `WA_ShowWithoutActivating` keeps the pet from grabbing keyboard focus when it appears.
- The POC does **not** set `WA_NoSystemBackground` or `WA_AlwaysShowToolTips`; only the two
  attributes above are used.

Paint with `QPainter` in `paintEvent`. The real `paintEvent` explicitly clears to transparent
first, then draws over it:

```python
def paintEvent(self, event):
    p = QPainter(self)
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    p.fillRect(self.rect(), Qt.transparent)            # wipe to fully transparent
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.setRenderHint(QPainter.Antialiasing)
    self._draw(p)                                       # dog, bed, bowl, ball, zzz
    p.end()
```

Because the background is translucent, only what you draw is visible; the rest is see-through.

---

## 2. Anchoring to the taskbar surface

The POC does **not** size the window to the taskbar band. It places a fixed-height strip
(`WIN_H = 95` px) that spans the full screen width and sits **above** the taskbar, so the dog's
feet land on the taskbar's top edge and it looks like the dog is standing on the taskbar.

Taskbar geometry is computed in Qt **logical** pixels (deliberately — see §4 on DPI):

```python
def get_taskbar_rect():
    """Return (left, top, right, bottom) of the taskbar in Qt logical pixels."""
    screen = QApplication.primaryScreen()
    sg = screen.geometry()           # full screen, logical px
    ag = screen.availableGeometry()  # area excluding the taskbar, logical px

    # QRect.bottom() == y + height - 1 (last included row); right() similar.
    if ag.bottom() < sg.bottom():        # taskbar at bottom (typical)
        tb_top    = ag.bottom() + 1      # first row of the taskbar
        tb_bottom = sg.bottom() + 1
        tb_left   = sg.left()
        tb_right  = sg.right() + 1
    else:                                # fallback — assume 48 px at bottom
        tb_bottom = sg.bottom() + 1
        tb_top    = tb_bottom - 48
        tb_left   = sg.left()
        tb_right  = sg.right() + 1
    return tb_left, tb_top, tb_right, tb_bottom
```

Window placement (`_place_window`): the window's bottom pixel row is made to land exactly on
`tb_top`, and the dog is drawn so its feet sit at `DOG_BASE = WIN_H` (the window's bottom):

```python
WIN_H   = 95
DOG_BASE = WIN_H                      # last painted row = WIN_H - 1, which maps to tb_top

def _place_window(self):
    wy = self.tb_top - WIN_H + 1      # last window row lands on tb_top
    self.setGeometry(0, wy, self.win_w, WIN_H)   # win_w == full screen width
    self._update_mask()
```

Notes and gotchas:
- The window always starts at `x = 0` and spans full width, so **window-local x == screen x**.
  The dog and the corner objects are drawn at their screen-x coordinates directly.
- This assumes a **bottom** taskbar (the usual case). The `get_taskbar_rect` fallback assumes a
  48 px bottom band if `availableGeometry` doesn't show a bottom inset. Left/right/top taskbars
  are not handled by the POC.
- The POC computes geometry once at startup. It does **not** re-anchor on resolution/DPI change
  (`screenAdded` / `geometryChanged` are not wired up). Add that if you need live re-anchoring.

---

## 3. Click-through, but only where it should be — **window mask, rebuilt every frame**

This is the crux, and the POC does it with **`setMask(region)`**, not a Win32 input-transparency
toggle. `setMask` clips both painting and the hit area to `region`. Anything outside the mask is
literally not part of the window, so clicks there fall through to the desktop/taskbar. Clicks
inside the mask arrive at `mousePressEvent`.

The POC rebuilds the mask **every tick** (~30 Hz) from the *current animated* bounding rects, so
the clickable area tracks the dog as it walks:

```python
def _update_mask(self):
    dx = int(self.dog_sx)
    if self.state in (State.SLEEPING, State.STRETCHING, State.SCRATCHING):
        dog_r = QRect(dx - 60, WIN_H - 38, 120, 38)     # curled-up footprint
    else:
        dog_r = QRect(dx - 52, WIN_H - 75, 104, 75)     # standing footprint

    decor_left  = self.bed_cx - 42
    decor_right = self.ball_cx + 12
    decor_r = QRect(decor_left, WIN_H - 25, decor_right - decor_left, 25)

    region = QRegion(dog_r) | QRegion(decor_r)

    # A thrown ball that's away from its home corner needs its own mask rect.
    if self.ball_visible and abs(self.ball_x - self.ball_cx) > 20:
        bx = int(self.ball_x)
        region |= QRegion(QRect(bx - 12, WIN_H - 20, 24, 20))

    self.setMask(region)
```

`_update_mask()` is called from `_on_tick()` every frame (the 33 ms timer), and also once in
`_place_window()`. Rebuilding a small union-of-rects region each frame is cheap here and does
**not** cause the jitter the old guidance warned about, because the painting is lightweight
procedural drawing (no per-frame bitmap blits).

Clicks are routed in `mousePressEvent`, which hit-tests by region in window-local coordinates
(left-click ball/bowl/dog, right-click → context menu):

```python
def mousePressEvent(self, event):
    lx, ly = event.pos().x(), event.pos().y()
    if event.button() == Qt.LeftButton:
        # ball at home corner -> throw it
        # bowl -> refill
        # otherwise on the dog -> EXCITED
        ...
    elif event.button() == Qt.RightButton:
        self._show_menu(event.globalPos())     # settings + Test menu
```

Why the mask approach is fine here:
- The interactive area is the dog plus three small corner objects. A union of 2–3 rectangles is
  trivial to rebuild at 30 Hz.
- Because the mask *is* the window, there's no separate hit-region to keep in sync — paint and
  input use the same clip.

> If you ever switch to heavy per-frame bitmap rendering and the mask rebuild becomes a
> bottleneck, the Win32 `WS_EX_LAYERED | WS_EX_TRANSPARENT` toggle (flip input-transparency off
> only while the cursor is over an interactive rect) is the standard alternative. The POC does
> not need it.

---

## 4. DPI: stay in logical pixels (no high-DPI scaling attribute)

The POC does **not** call `QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)`. It
deliberately does everything in Qt **logical** pixels: `setGeometry` and the taskbar rect both
come from `QScreen.geometry()` / `availableGeometry()`, which are in the same logical space, so
there's no physical-vs-logical mismatch. (The original code comment notes this is specifically
to avoid a DPI mismatch you'd get from mixing `SHAppBarMessage` physical pixels with Qt logical
pixels.) If you change this, re-check the taskbar math.

---

## 5. Keeping it above other windows — the POC **does** reassert topmost

`WindowStaysOnTopHint` keeps the overlay above normal windows, but the POC also actively
reasserts HWND_TOPMOST: once at startup, and again every 180 ticks (~6 s) from `_on_tick`:

```python
def _assert_topmost(self):
    hwnd = int(self.winId())
    ctypes.WinDLL("user32").SetWindowPos(
        hwnd, -1, 0, 0, 0, 0,                 # -1 == HWND_TOPMOST
        0x0001 | 0x0002 | 0x0010)             # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
```

```python
# in _on_tick, after updating state:
if self._ticks % 180 == 0:
    self._assert_topmost()
```

This is the opposite of "don't reassert by default" — the POC found periodic reassertion
necessary to stay reliably on top of the taskbar, and it uses `SWP_NOACTIVATE` so it never
steals focus. It will still sit under true exclusive-fullscreen apps, which is usually desirable.

---

## 6. Verify the window

- The dog and the bed/bowl/ball should be visible sitting on the taskbar; everything else is
  see-through.
- Clicking the desktop or taskbar **outside** the dog/objects should behave normally (proves the
  mask makes those areas click-through).
- Clicking the dog should trigger the excited animation; right-clicking it should open the menu
  (proves the mask covers the interactive rects).
- Confirm the overlay does **not** appear as a taskbar button or in alt-tab (proves `Qt.Tool`).
