"""Phase 4a verification harness (dev tool — not part of the app).

Part 1 — recognizer unit checks (synthetic coordinates, no UI):
  perfect circling completes at ~3 loops; reversing direction cancels;
  the arming window times out; leaving the ring past the grace disarms.

Part 2 — end-to-end on the REAL app with the REAL cursor:
  a synthesized click on the dog arms the recognizer, SetCursorPos then
  drives the cursor in ~3.2 circles around the dog; ROLL_OVER must fire,
  show on the HUD (STATE/ANIM/GESTURE), keep the dog clickable (mask probe),
  and settle back to SLEEPING. With the toggle off the same gesture must do
  nothing; Test: roll over must force-fire regardless.

Writes verify/phase4/phase4-log.txt; exit code 0 on success.
Run: python tools/verify_phase4.py
"""

import os
import sys
import math
import ctypes
import ctypes.wintypes
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "verify", "phase4")
os.makedirs(OUT, exist_ok=True)

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="persi-verify-")

log_lines = []
_failures = []


def log(msg):
    print(msg, flush=True)
    log_lines.append(msg)


def check(name, cond, detail=""):
    log(f"{'PASS' if cond else 'FAIL'}  {name}{('  [' + detail + ']') if detail else ''}")
    if not cond:
        _failures.append(name)


# ── Part 1: recognizer unit checks ───────────────────────────────────────────

from gestures import CircleGestureRecognizer, TWO_PI


def feed_circle(rec, loops, radius=80.0, step=0.25, cx=500.0, cy=500.0):
    ang = 0.0
    fired = False
    n = int(loops * TWO_PI / step)
    for _ in range(n):
        ang += step
        x = cx + radius * math.cos(ang)
        y = cy + radius * math.sin(ang)
        if rec.tick(cx, cy, x, y):
            fired = True
            break
    return fired, ang / TWO_PI


rec = CircleGestureRecognizer()
rec.arm()
fired, at_loops = feed_circle(rec, 4.0)
check("unit: 3 consistent loops complete the gesture",
      fired and 2.9 < at_loops < 3.4, f"fired at {at_loops:.2f} loops")

rec.arm()
fired1, _ = feed_circle(rec, 1.5)
ang = 1.5 * TWO_PI
reversed_fired = False
for _ in range(int(3.5 * TWO_PI / 0.25)):
    ang -= 0.25
    x = 500 + 80 * math.cos(ang)
    y = 500 + 80 * math.sin(ang)
    if rec.tick(500, 500, x, y):
        reversed_fired = True
        break
check("unit: reversing direction cancels accumulation",
      not fired1 and not reversed_fired and rec.armed)
rec.disarm()

rec.arm()
timed_out = False
for _ in range(rec.WINDOW_TICKS + 5):
    rec.tick(500, 500, 560, 500)        # cursor parked in the ring
if not rec.armed:
    timed_out = True
check("unit: arming window times out", timed_out)

rec.arm()
for _ in range(rec.OFF_RING_GRACE + 5):
    rec.tick(500, 500, 1500, 500)       # far outside the ring
check("unit: leaving the ring past the grace disarms", not rec.armed)


# ── Part 2: end-to-end on the real app ───────────────────────────────────────

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QEvent, QPoint, Qt
from PyQt5.QtGui import QMouseEvent

app = QApplication(sys.argv)

import biscuit
from biscuit import State, WIN_H

dog = biscuit.Biscuit()
dog._greet_timer.stop()      # keep the launch greet out of this harness


def shot(name):
    screen = QApplication.primaryScreen()
    x = max(0, int(dog.dog_sx) - 170)
    y = max(0, dog.tb_top - 260)
    pm = screen.grabWindow(0, x, y, 340, 270)
    pm.save(os.path.join(OUT, name + ".png"))


def hwnd_at(x, y):
    pt = ctypes.wintypes.POINT(int(x), int(y))
    return ctypes.windll.user32.WindowFromPoint(pt)


def reset_dog():
    dog.state = State.SLEEPING
    dog.returning = False
    dog.task_phase = 0
    dog.task_frames = 0
    dog.tongue = False
    dog.bounce_val = 0.0
    dog.dog_sx = float(dog.bed_cx)
    dog.fidgets.cancel()
    dog.gesture.disarm()
    dog._sleep_timer.stop()


def click_dog():
    ev = QMouseEvent(QEvent.MouseButtonPress, QPoint(int(dog.dog_sx), WIN_H - 30),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    dog.mousePressEvent(ev)


class CursorCircler:
    """Drives the real cursor in circles around the dog at ~25 ms steps."""

    def __init__(self, loops=3.4, radius=80, step=0.22):
        self.ang = 0.0
        self.left = int(loops * TWO_PI / step)
        self.step = step
        self.radius = radius
        self.timer = QTimer(dog)
        self.timer.timeout.connect(self._tick)

    def start(self):
        self.timer.start(25)

    def _tick(self):
        if self.left <= 0 or not self.timer.isActive():
            self.timer.stop()
            return
        self.left -= 1
        self.ang += self.step
        x = int(dog.dog_sx + self.radius * math.cos(self.ang))
        y = int((dog.tb_top - 30) + self.radius * math.sin(self.ang))
        ctypes.windll.user32.SetCursorPos(x, y)


_steps = []


def step(delay_ms):
    def deco(fn):
        _steps.append((delay_ms, fn))
        return fn
    return deco


def run_steps():
    def advance():
        if not _steps:
            finish()
            return
        delay, fn = _steps.pop(0)
        QTimer.singleShot(delay, lambda: (fn(), advance()))
    advance()


seen = {"rollover": False, "armed_hud": "", "max_loops": 0.0}
_watch = QTimer(dog)


def _watch_tick():
    if dog.state == State.ROLL_OVER:
        seen["rollover"] = True
    if dog.gesture.armed:
        seen["max_loops"] = max(seen["max_loops"], dog.gesture.loops)
        for label, val in getattr(dog._hud, "_lines", []):
            if label == "GESTURE" and val != "-":
                seen["armed_hud"] = val


_circlers = []                   # keep refs: PyQt connections to bound methods
                                 # are weak, an unreferenced circler is GC'd


def start_circling():
    c = CursorCircler()
    _circlers.append(c)
    c.start()


@step(500)
def t_gesture_fires():
    reset_dog()
    ctypes.windll.user32.SetCursorPos(int(dog.dog_sx), dog.tb_top - 30)
    seen.update(rollover=False, armed_hud="", max_loops=0.0)
    _watch.timeout.connect(_watch_tick)
    _watch.start(20)
    click_dog()                  # arms the recognizer (and excites the dog)
    start_circling()


@step(2000)
def t_mid_gesture_shot():
    pass                         # circling still in progress; nothing to assert yet


@step(1500)
def t_check_fired():
    check("real cursor circling fires ROLL_OVER",
          seen["rollover"], f"state={dog.state.name}")
    check("HUD GESTURE line live while armed",
          seen["armed_hud"] != "" and seen["max_loops"] > 1.0,
          f"hud='{seen['armed_hud']}' max_loops={seen['max_loops']:.1f}")


@step(800)
def t_belly_shot():
    # Fire again via Test to capture the belly-up frame deterministically
    reset_dog()
    dog._test_roll_over()


@step(1600)
def t_take_belly_shot():
    shot("roll-over-belly-up")
    on_dog = hwnd_at(dog.dog_sx, dog.tb_top - 15)
    check("dog clickable during ROLL_OVER (mask intact)",
          on_dog == int(dog.winId()) and dog.state == State.ROLL_OVER,
          f"state={dog.state.name}")


@step(3500)
def t_returns_to_sleep():
    check("ROLL_OVER settles back to SLEEPING",
          dog.state == State.SLEEPING, f"state={dog.state.name}")


@step(300)
def t_toggle_off():
    reset_dog()
    ctypes.windll.user32.SetCursorPos(dog.sw // 2, 80)
    dog.settings.set("command.roll_over", False)
    ctypes.windll.user32.SetCursorPos(int(dog.dog_sx), dog.tb_top - 30)
    seen["rollover"] = False
    click_dog()
    start_circling()


@step(3500)
def t_toggle_off_check():
    check("toggle off: full circling never fires ROLL_OVER",
          not seen["rollover"], f"state={dog.state.name}")
    ctypes.windll.user32.SetCursorPos(dog.sw // 2, 80)


@step(300)
def t_test_bypass():
    reset_dog()                  # toggle still off
    dog._test_roll_over()
    check("Test: roll over force-fires with toggle off",
          dog.state == State.ROLL_OVER)
    dog.settings.set("command.roll_over", True)
    _watch.stop()
    reset_dog()


def finish():
    log("")
    if _failures:
        log("FAILURES:")
        for f in _failures:
            log(f"  - {f}")
    else:
        log("ALL CHECKS PASSED")
    with open(os.path.join(OUT, "phase4-log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    app.exit(1 if _failures else 0)


run_steps()
sys.exit(app.exec_())
