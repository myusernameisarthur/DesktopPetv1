# Biscuit 🐾

> A transparent, always-on-top Windows desktop pet — an animated sausage dog who lives on your taskbar.

Biscuit sits in the bottom-right corner of your screen, just above the clock. He sleeps, breathes, yawns, goes for sniff walks, scratches his ear, chews bones, fetches the ball when you throw it, and gently reminds you to stretch and drink water. He is drawn entirely with Qt's `QPainter` — no sprites yet, just geometry. The plan is to eventually replace the placeholder art with real illustrations.

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
| Right-click menu | Pause, startup, reminder toggles, full test suite |
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
python -m PyInstaller --onefile --windowed --name Biscuit biscuit.py
# → dist/Biscuit.exe
```

---

## Project background

This was built in a single session with Claude as a coding partner. Arthur wanted a desktop pet for Windows — specifically a dachshund — without any prior Python or Qt experience. Every decision was made collaboratively, with Claude writing code and Arthur directing behavior, visual feel, and priorities.

See [DEVLOG.md](DEVLOG.md) for the full step-by-step development history.

See [HANDOFF.md](HANDOFF.md) for a complete technical briefing for anyone continuing this project.

---

## File structure

```
biscuit.py     — entire application (~900 lines, single file)
Biscuit.spec   — PyInstaller build spec
README.md      — this file
DEVLOG.md      — full development log with decisions and reasoning
HANDOFF.md     — technical briefing for new contributors / AI instances
.gitignore     — excludes build artifacts
```

---

## Roadmap

- [ ] Real sprite art (replace QPainter placeholder geometry)
- [ ] Optional sound effects (off by default)
- [ ] Dream twitching while asleep
- [ ] Chasing tail idle behavior  
- [ ] Settings persistence (JSON config file)
- [ ] Multi-monitor awareness
- [ ] Configurable reminder intervals
