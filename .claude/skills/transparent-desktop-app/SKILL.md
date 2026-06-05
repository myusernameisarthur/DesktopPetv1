---
name: transparent-desktop-app
description: >
  Build transparent, always-on-top, click-through desktop overlay apps on Windows with
  Python + PyQt5, packaged to a single exe with PyInstaller. Covers the overlay window
  (frameless, translucent, taskbar-anchored, click-through except over interactive sprites),
  sprite/animation pipelines, a behavior state machine, manifest-driven asset loading,
  and packaging. Trigger: "desktop pet", "taskbar overlay", "always-on-top widget",
  "transparent desktop app", "click-through window", "PyQt5 overlay", "system tray companion".
---

# Transparent Desktop App (PyQt5 Overlay)

Build native Windows overlay apps that float above the desktop: transparent background,
always on top, click-through everywhere except the interactive sprites. The reference
implementation is a desktop pet that sits on the taskbar, but the patterns apply to any
ambient overlay (status widget, HUD, companion).

This skill targets **Python 3 + PyQt5**, packaged as a **single exe via PyInstaller**.

---

## STOP: Three things break this kind of app. Read the matching reference first.

1. **Click-through hit-testing.** A naive transparent window either eats every click on the
   desktop or passes every click through (so you can never click the sprite). Getting clicks
   to land *only* on the sprite/objects is the hardest part. Read
   [overlay-window.md](references/overlay-window.md) before touching window flags.

2. **Spritesheet loading.** A few pixels off on frame size silently corrupts every animation
   and the damage compounds. Read [sprites-and-animation.md](references/sprites-and-animation.md)
   before loading any spritesheet. **Measure the asset. Never guess frame dimensions.**

3. **PyInstaller asset paths.** Code that finds `assets/dog.png` in dev throws "file not found"
   once frozen into an exe, because the working directory changes. Read
   [packaging-and-testing.md](references/packaging-and-testing.md) before the first build.

---

## Reference Files

Read the relevant one BEFORE working on that feature.

| When working on... | Read first |
|--------------------|------------|
| Window flags, transparency, always-on-top, taskbar geometry, click-through | [overlay-window.md](references/overlay-window.md) |
| Loading spritesheets, slicing frames, animation timing, animation state machine | [sprites-and-animation.md](references/sprites-and-animation.md) |
| assets.json manifest, behavior scheduler, idle/trigger/timer logic | [assets-and-behaviors.md](references/assets-and-behaviors.md) |
| PyInstaller packaging, bundling assets, screenshot testing, the right-click test menu | [packaging-and-testing.md](references/packaging-and-testing.md) |

---

## Architecture (the standard shape)

```
project/
├── main.py                 # Entry point: QApplication, create overlay, start event loop
├── overlay.py              # The transparent click-through window (QWidget)
├── pet.py                  # The sprite actor: position, current frame, draw
├── behaviors.py            # Behavior state machine + scheduler (timers, triggers)
├── animation.py            # Spritesheet slicing + frame playback
├── assets_manifest.py      # Loads assets.json, resolves frozen vs dev paths
├── settings_menu.py        # Right-click menu: toggles + a "Test" section per behavior
├── assets/
│   ├── assets.json         # Index of every sprite + its frames/animations
│   └── *.png               # Spritesheets / frames
└── build.spec              # PyInstaller spec (one-file, assets bundled)
```

Keep responsibilities separate. The window (`overlay.py`) only knows how to be transparent
and route input. It does not know what a "sniff walk" is. The behavior layer (`behaviors.py`)
drives state and never touches Win32 flags. This split is what lets you add behavior #13
without breaking the windowing.

---

## Window model (one screen-wide overlay)

The proven model for a taskbar pet is a **single frameless translucent window spanning the
full screen width**, sitting just above the taskbar surface (the POC uses a fixed `WIN_H = 95`
px strip so the dog's feet land on the taskbar's top edge). Everything draws into that one
window. **In the POC, click-through is solved with a per-frame window mask** (`setMask`),
*not* by polling the cursor and toggling Win32 input transparency — the mask is rebuilt every
tick from the dog's current bounding rects. Details (and when the Win32 toggle would be the
alternative) are in [overlay-window.md](references/overlay-window.md).

Required window setup, as used in the POC:

```python
self.setWindowFlags(
    Qt.FramelessWindowHint
    | Qt.WindowStaysOnTopHint
    | Qt.Tool                      # keep it out of the taskbar button list and alt-tab
    | Qt.NoDropShadowWindowHint    # no shadow box around the invisible window
)
self.setAttribute(Qt.WA_TranslucentBackground)   # transparent background
self.setAttribute(Qt.WA_ShowWithoutActivating)   # don't steal focus on show
```

`Qt.Tool` matters: without it the overlay itself shows up as a taskbar button.

---

## Behavior model (default-idle + weighted triggers)

The pet has one **default resting state** (e.g. sleeping on its bed) that it returns to after
any behavior finishes. Other behaviors fire from three sources:

- **Timers** (stretch every 30 min, water every 60 min)
- **User input** (click the sprite, click the ball)
- **Ambient/random** (occasional sniff walk, scratch), weighted so the default dominates

One behavior runs at a time. A behavior is a small state object with `enter()`, `update(dt)`,
and `exit()`, and it reports when it's done so the scheduler can return to idle. Full pattern
in [assets-and-behaviors.md](references/assets-and-behaviors.md).

---

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| Whole-window `WA_TransparentForInput` | Sprite becomes unclickable too | Clip the window to the interactive rects with `setMask` (what the POC does), or toggle input transparency by cursor region (see overlay-window.md) |
| Guessing frame width from eyeballing | Silent animation corruption | Measure the PNG; verify `imgW = frameW × cols + spacing×(cols-1)` |
| Hard-coded `assets/dog.png` paths | Works in dev, crashes as exe | Resolve paths via `sys._MEIPASS` helper (packaging.md) |
| `time.sleep()` for animation timing | Freezes the UI thread | Drive frames from a `QTimer` and a delta clock |
| One giant `overlay.py` | Windowing and behaviors entangle, fragile | Split window / actor / behavior / animation |
| Repainting the full screen-wide window every tick | CPU spikes, fan noise (with heavy bitmap blits) | `update(QRect)` only the dirty sprite region — *note: the POC repaints the full window every tick and it's fine, because its procedural drawing is cheap* |
| New behavior = edit five files | Slows iteration | Behaviors are self-contained classes registered in one place |
| No test triggers | Can't reproduce a 60-min timer behavior on demand | Keep a "Test" submenu that fires any behavior instantly |

---

## Workflow (how to build with this skill)

Mirror the incremental, verify-each-step loop. Do not build everything at once.

1. **Manifest first.** Study the art in `assets/`, write `assets.json` indexing every sprite,
   its frame grid, and named animations. (assets-and-behaviors.md)
2. **Bare window.** Frameless, translucent, always-on-top, anchored to the taskbar. Verify it's
   invisible-but-present and doesn't steal desktop clicks. (overlay-window.md)
3. **Static sprite.** Draw one frame at the resting position. Verify it sits on the taskbar.
4. **One animation.** Slice the spritesheet, play the idle/breathing loop from a QTimer. (sprites-and-animation.md)
5. **Click-through hit-testing.** Cursor over sprite = clickable; everywhere else = pass-through. (overlay-window.md)
6. **Behavior scheduler.** Default-idle + one triggered behavior end to end. (assets-and-behaviors.md)
7. **Right-click menu** with toggles and a Test section per behavior. (packaging-and-testing.md)
8. **Add remaining behaviors** one at a time, each verified via its test trigger.
9. **Package** to a single exe and verify assets load when frozen. (packaging-and-testing.md)

Rebuild the exe after a change only when verifying packaging; for behavior iteration, run
`python main.py` directly. It's far faster than a PyInstaller build each loop.

---

## Remember

PyQt5 gives you the window, the timer, and the painter. The overlay illusion (transparent,
on top, click-through-except-sprite) and the behavior system are yours to architect. Keep the
window dumb, keep behaviors self-contained, and measure every spritesheet before you load it.
