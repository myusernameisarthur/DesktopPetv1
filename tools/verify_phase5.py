"""Phase 5 verification harness (dev tool — not part of the app).

Drives the REAL app to prove the four new behaviors:
  - bark: Test-fired one-shot, head-back + open mouth, settles back to sleep;
  - beg: fired by a real double-click on the dog, honors its switch, Test
    bypasses the switch, reminders can't interrupt it;
  - greet: fires on launch path and on cursor-return-after-idle (thresholds
    shrunk for the test), honors its switch and cooldown, optionally chains
    into the bark;
  - zoomies: dash gait speed measured, reachable from the ambient picker,
    hands off to TASK_RETURN (plod home).

Writes verify/phase5/phase5-log.txt; exit code 0 on success.
Run: python tools/verify_phase5.py
"""

import os
import sys
import time
import ctypes
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "verify", "phase5")
os.makedirs(OUT, exist_ok=True)

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="persi-verify-")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QEvent, QPoint, Qt
from PyQt5.QtGui import QMouseEvent

app = QApplication(sys.argv)

import biscuit
from biscuit import State, GAITS, WIN_H

dog = biscuit.Biscuit()
dog._greet_timer.stop()      # the harness fires the launch path explicitly

log_lines = []
_failures = []


def log(msg):
    print(msg, flush=True)
    log_lines.append(msg)


def check(name, cond, detail=""):
    log(f"{'PASS' if cond else 'FAIL'}  {name}{('  [' + detail + ']') if detail else ''}")
    if not cond:
        _failures.append(name)


def cursor_far():
    ctypes.windll.user32.SetCursorPos(dog.sw // 2, 80)


def reset_dog():
    dog.state = State.SLEEPING
    dog.returning = False
    dog.task_phase = 0
    dog.task_frames = 0
    dog.tongue = False
    dog.bounce_val = 0.0
    dog.dog_sx = float(dog.bed_cx)
    dog.stretch_pending = False
    dog.water_pending = False
    dog.fidgets.cancel()
    dog.gesture.disarm()
    dog._sleep_timer.stop()


def shot(name):
    screen = QApplication.primaryScreen()
    x = max(0, int(dog.dog_sx) - 170)
    y = max(0, dog.tb_top - 260)
    pm = screen.grabWindow(0, x, y, 340, 270)
    pm.save(os.path.join(OUT, name + ".png"))


def double_click_dog():
    ev = QMouseEvent(QEvent.MouseButtonDblClick,
                     QPoint(int(dog.dog_sx), WIN_H - 30),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    dog.mouseDoubleClickEvent(ev)


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


# ── bark ─────────────────────────────────────────────────────────────────────

@step(500)
def t_bark():
    cursor_far()
    reset_dog()
    dog._test_bark()
    check("Test: bark fires BARKING",
          dog.state == State.BARKING and dog.current_anim() == "bark")


@step(500)
def t_bark_shot():
    shot("bark")


@step(2000)
def t_bark_settles():
    check("bark settles back to SLEEPING",
          dog.state == State.SLEEPING, f"state={dog.state.name}")


# ── beg ──────────────────────────────────────────────────────────────────────

@step(300)
def t_beg_doubleclick():
    reset_dog()
    double_click_dog()
    check("double-click on dog fires BEG",
          dog.state == State.BEG and dog.current_anim() == "beg-sit-up")


@step(1100)
def t_beg_shot():
    shot("beg-sit-up")


@step(2500)
def t_beg_settles():
    check("beg settles back to SLEEPING",
          dog.state == State.SLEEPING, f"state={dog.state.name}")


@step(200)
def t_beg_switch():
    reset_dog()
    dog.settings.set("command.beg", False)
    double_click_dog()
    off_ok = dog.state != State.BEG
    dog._test_beg()
    bypass_ok = dog.state == State.BEG
    check("beg honors its switch; Test bypasses", off_ok and bypass_ok)
    dog.settings.set("command.beg", True)


@step(200)
def t_beg_uninterruptible():
    # already BEG from previous step
    dog.stretch_pending = True
    dog._check_pending()
    check("reminder can't interrupt BEG (stays pending)",
          dog.state == State.BEG and dog.stretch_pending)
    dog.stretch_pending = False
    reset_dog()


# ── greet ────────────────────────────────────────────────────────────────────

@step(300)
def t_greet_launch():
    reset_dog()
    dog._launch_greet()              # same path as the startup timer
    check("launch path fires GREETING",
          dog.state == State.GREETING and dog.current_anim() == "greet-wag")
    dog._greet_bark = True           # force the bark chain deterministically


@step(1200)
def t_greet_shot():
    shot("greet-wag")


@step(2200)
def t_greet_bark_chain():
    check("greet chains into BARKING when flagged",
          dog.state == State.BARKING, f"state={dog.state.name}")


@step(2200)
def t_greet_chain_settles():
    check("greet+bark settles back to SLEEPING",
          dog.state == State.SLEEPING, f"state={dog.state.name}")


@step(200)
def t_greet_switch():
    reset_dog()
    dog.settings.set("reactive.greet", False)
    dog._launch_greet()
    check("greet honors its switch", dog.state == State.SLEEPING)
    dog.settings.set("reactive.greet", True)


@step(200)
def t_greet_idle_return_setup():
    reset_dog()
    dog.greet_idle_s = 2.0           # shrink the idle threshold for the test
    dog.greet_cooldown_s = 0.0
    cursor_far()


@step(500)
def t_greet_idle_return_move():
    # Back-date the last cursor move so the next real move reads as a return
    # after a long idle (immune to the human mouse moving during the test).
    dog._last_cursor_move_t = time.monotonic() - 100.0
    ctypes.windll.user32.SetCursorPos(dog.sw // 2 - 200, 120)   # the "return"


@step(700)
def t_greet_idle_return_check():
    check("cursor return after idle gap fires GREETING",
          dog.state in (State.GREETING, State.BARKING),
          f"state={dog.state.name}")
    dog._greet_bark = False
    dog.greet_cooldown_s = 600.0     # now test the rate limit
    reset_dog()
    cursor_far()


@step(500)
def t_greet_cooldown_move():
    dog._last_cursor_move_t = time.monotonic() - 100.0
    ctypes.windll.user32.SetCursorPos(dog.sw // 2 - 200, 120)


@step(700)
def t_greet_cooldown_check():
    check("return-greet rate-limited by cooldown",
          dog.state == State.SLEEPING, f"state={dog.state.name}")


# ── zoomies ──────────────────────────────────────────────────────────────────

zoom_probe = {}


@step(300)
def t_zoomies():
    reset_dog()
    dog._test_zoomies()
    check("Test: zoomies fires ZOOMIES",
          dog.state == State.ZOOMIES and dog.current_anim() == "dash")


@step(400)
def t_zoomies_probe_begin():
    zoom_probe["x"] = dog.dog_sx
    zoom_probe["ticks"] = dog._ticks


@step(900)
def t_zoomies_speed():
    dticks = max(1, dog._ticks - zoom_probe["ticks"])
    px_t = abs(dog.dog_sx - zoom_probe["x"]) / dticks
    g = GAITS["dash"]
    check("zoomies dashes at the dash gait speed",
          dog.state == State.ZOOMIES and abs(px_t - g.speed) / g.speed < 0.15,
          f"{px_t:.2f}px/tick (expect {g.speed})")
    shot("zoomies-dash")


@step(100)
def t_zoomies_handoff():
    # Shorten the episode: end after the current dash, with a nearby dest
    dog.state_frames = dog.task_phase + 1
    dog.zoom_dest = dog.dog_sx - 10 * dog.facing
    zoom_probe["saw_return"] = False
    poll = QTimer(dog)
    poll.timeout.connect(
        lambda: zoom_probe.__setitem__(
            "saw_return",
            zoom_probe["saw_return"] or dog.state == State.TASK_RETURN))
    poll.start(25)
    zoom_probe["poll"] = poll


@step(2500)
def t_zoomies_handoff_check():
    zoom_probe["poll"].stop()
    check("zoomies hands off to TASK_RETURN (plod home)",
          zoom_probe["saw_return"], f"state={dog.state.name}")
    reset_dog()


@step(200)
def t_zoomies_ambient():
    reset_dog()
    for k in ("idle.wander_walk", "idle.scratch", "idle.chew",
              "idle.sniff_walk"):
        dog.settings.set(k, False)
    dog._start_walk()
    check("ambient picker reaches zoomies (only switch on)",
          dog.state == State.ZOOMIES, f"state={dog.state.name}")
    for k in ("idle.wander_walk", "idle.scratch", "idle.chew",
              "idle.sniff_walk"):
        dog.settings.set(k, True)
    reset_dog()


def finish():
    log("")
    if _failures:
        log("FAILURES:")
        for f in _failures:
            log(f"  - {f}")
    else:
        log("ALL CHECKS PASSED")
    with open(os.path.join(OUT, "phase5-log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    app.exit(1 if _failures else 0)


run_steps()
sys.exit(app.exec_())
