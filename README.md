# Biscuit 🐾

> A transparent, always-on-top Windows desktop pet — an animated sausage dog who lives on your taskbar.

Biscuit (a.k.a. **Persi**) sits in the bottom-right corner of your screen, just above the clock. He sleeps, breathes, yawns, goes for sniff walks, scratches his ear, chews bones, fetches the ball when you throw it, begs, does zoomies, climbs up onto the taskbar when you launch him, and gently reminds you to stretch and drink water. He now renders from **real pixel-art sprites** (34 animation clips), with the original `QPainter` geometry kept as a switchable "Classic shapes" renderer. You can also resize him from 75% to 200%.

---

## What it looks like

```
[taskbar .............. 🛏️ 🥣 🔴]
                          ^Biscuit sleeps here
```

A small sausage dog shape (elongated oval body, round head, floppy ear, four rounded-rect legs, QPainterPath tail) rests on a white oval cushion in the bottom-right corner. A water bowl and a red ball sit beside him.

---

## Features

| Feature | Detail |
|---|---|
| Always on top | Sits above everything including the taskbar clock |
| Click-through | Window is transparent; only Biscuit's bounding box captures clicks |
| Sleeping | Breathing animation (body scale), floating `z` bubbles |
| Corner home | Bed, water bowl, ball rendered at fixed positions above the tray |
| Cursor awareness | Dog wakes and faces cursor when it comes within 150 px |
| Left-click dog | Excited bounce + tongue, 2.5 s |
| Normal walk | Dog roams the taskbar and returns to bed |
| **Scratch** | Dog lies down, shakes, back leg kicks at ear for 3–4 s |
| **Chew bone** | Dog stands and gnaws a bone shape for 8–10 s |
| **Sniff walk** | Slow walk with nose down, pausing every 20–30 px to investigate |
| **Fetch** | Click ball → it teleports; dog fetches it and brings it back |
| **Stretch reminder** | Every 30 min: dog stretches body and yawns |
| **Water reminder** | Every 60 min: dog walks to bowl, drinks, bowl empties |
| Bowl refill | Click bowl to refill (grey → blue) |
| **Pixel-art sprites** | 34 animation clips drive every state; switchable to the original "Classic shapes" geometry in the Art menu |
| **Size toggle** | Art menu: 75% / 100% / 125% / 150% / 200%, persisted |
| **Climb on launch** | Hauls himself up from behind the taskbar when the app starts, then greets |
| **Beg / greet / zoomies** | Double-click to beg; greets on launch and your return; rare zoomie dashes |
| Right-click menu | Pause, startup, art renderer + size, grouped behavior toggles, full test suite |
| Settings persistence | Every toggle + art choices saved to `%APPDATA%\Persi\settings.json` |
| Test triggers | All behaviors triggerable immediately from the menu |

---

## Running from source

```bash
pip install PyQt5
python biscuit.py
```

Python 3.11+, Windows only.

## Building the exe

```bash
pip install pyinstaller
python -m PyInstaller Biscuit.spec
# → dist/Biscuit.exe  (the spec bundles assets/ — don't use the bare --onefile form, it omits the sprites)
```

---

## Project background

This was built in a single session with Claude as a coding partner. Arthur wanted a desktop pet for Windows — specifically a dachshund — without any prior Python or Qt experience. Every decision was made collaboratively, with Claude writing code and Arthur directing behavior, visual feel, and priorities.

See [DEVLOG.md](DEVLOG.md) for the full step-by-step development history.

See [HANDOFF.md](HANDOFF.md) for a complete technical briefing for anyone continuing this project.

---

## File structure

```
biscuit.py     — app + state machine + renderers (~1800 lines)
fidgets.py     — idle micro-behavior (fidget) engine
gestures.py    — roll-over circle-gesture recognizer
settings.py    — persisted toggles + art kit/scale (%APPDATA%\Persi)
sprites.py     — manifest-driven sprite renderer + kit discovery
debug_hud.py   — developer state HUD (toggle in the menu)
assets/        — sprite frames, props, palette, generated manifest.json
tools/art/     — art pipeline: pack.py (manifest gen), artlib.py, batch0.py
tools/         — verify_phase*.py, smoke_phase6.py
docs/          — roadmap, phase reports, animation inventory
OUTPUTS/persi-art/ — art work queue (NEXT-STEPS, OPEN-ITEMS, previews)
Biscuit.spec   — PyInstaller build spec (bundles assets/)
README.md / DEVLOG.md / HANDOFF.md — overview / history / technical briefing
.gitignore     — excludes build artifacts
```

---

## Roadmap

See `docs/persi-roadmap.md` for the full phased plan. Status in brief:

- [x] Idle micro-behaviors / fidgets (Phase 1)
- [x] Settings persistence — every behavior toggleable (Phase 2)
- [x] Distinct gaits (Phase 3)
- [x] Roll-over command gesture (Phase 4a; type-along + window-bark designed, deferred)
- [x] Beg, greet, zoomies — behavior list frozen (Phase 5)
- [x] Real sprite art in-app + size/kit toggles + startup climb (Phase 6 code)
- [ ] Regenerate the 19 placeholder clips + the `climb-up` clip (Phase 6 art gate)
- [ ] Multi-monitor / DPI correctness, perf pass, HUD off by default (Phase 7)
- [ ] Code-sign, installer, auto-start, updates (Phase 8)
- [ ] Optional sound effects (off by default)
