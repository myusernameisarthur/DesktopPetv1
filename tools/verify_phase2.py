"""Phase 2 verification harness (dev tool — not part of the app).

Redirects %APPDATA% to a temp dir (so the user's real settings are untouched),
then drives the REAL app to prove:
  1. defaults load on first run; toggles persist to settings.json and survive
     a "restart" (a fresh Settings instance);
  2. a corrupt settings file falls back to defaults;
  3. every behavior reads its switch before firing (ambient picks, reminders,
     cursor alert, click-excited, ball-fetch, both fidget poses);
  4. the Test menu force-fires regardless of switches;
  5. the right-click menu builds with grouped checkable toggles that reflect
     the stored values.

Writes verify/phase2/phase2-log.txt; exit code 0 on success.
Run: python tools/verify_phase2.py
"""

import os
import sys
import json
import time
import ctypes
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "verify", "phase2")
os.makedirs(OUT, exist_ok=True)

# Isolate the settings store BEFORE the app modules are imported.
TMP_APPDATA = tempfile.mkdtemp(prefix="persi-verify-")
os.environ["APPDATA"] = TMP_APPDATA
SETTINGS_FILE = os.path.join(TMP_APPDATA, "Persi", "settings.json")

from PyQt5.QtWidgets import QApplication, QMenu
from PyQt5.QtCore import QTimer, QEvent, QPoint, Qt
from PyQt5.QtGui import QMouseEvent

app = QApplication(sys.argv)

import biscuit
from biscuit import State, WIN_H
from settings import Settings, DEFAULTS

dog = biscuit.Biscuit()

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


def cursor_near_dog():
    ctypes.windll.user32.SetCursorPos(int(dog.dog_sx) + 60, dog.tb_top - 25)


def reset_dog():
    """Put the dog back in the default resting state between tests."""
    dog.state = State.SLEEPING
    dog.returning = False
    dog.task_phase = 0
    dog.task_frames = 0
    dog.stretch_factor = 0.0
    dog.tongue = False
    dog.bounce_val = 0.0
    dog.dog_sx = float(dog.bed_cx)
    dog.ball_x = float(dog.ball_cx)
    dog.ball_visible = True
    dog.stretch_pending = False
    dog.water_pending = False
    dog.fidgets.cancel()
    dog.fidgets.rate_mult = 1.0
    dog._sleep_timer.stop()


def set_all(value):
    for key in DEFAULTS:
        if key != "debug.hud":
            dog.settings.set(key, value)


def left_click(x, y):
    ev = QMouseEvent(QEvent.MouseButtonPress, QPoint(int(x), int(y)),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    dog.mousePressEvent(ev)


# ── step runner ──────────────────────────────────────────────────────────────

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


# ── tests ────────────────────────────────────────────────────────────────────

@step(400)
def t_defaults():
    cursor_far()
    check("fresh start uses defaults",
          all(dog.settings.get(k) == v for k, v in DEFAULTS.items()))


@step(100)
def t_persistence():
    dog.settings.set("idle.scratch", False)
    on_disk = json.load(open(SETTINGS_FILE, encoding="utf-8"))
    fresh = Settings()                      # simulates an app restart
    check("toggle persists to disk and survives restart",
          on_disk["idle.scratch"] is False and fresh.get("idle.scratch") is False)
    dog.settings.set("idle.scratch", True)


@step(100)
def t_corrupt_file():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
        fh.write("{not json!!")
    fresh = Settings()
    ok = all(fresh.get(k) == v for k, v in DEFAULTS.items())
    check("corrupt settings file falls back to defaults", ok)
    dog.settings.save()                     # heal the file from live values


@step(100)
def t_ambient_all_off():
    reset_dog()
    for k in ("idle.wander_walk", "idle.scratch", "idle.chew", "idle.sniff_walk"):
        dog.settings.set(k, False)
    dog._start_walk()
    check("ambient all off: stays asleep, timer re-armed",
          dog.state == State.SLEEPING and dog._sleep_timer.isActive())


@step(100)
def t_ambient_only_chew():
    reset_dog()
    dog.settings.set("idle.chew", True)
    dog._start_walk()
    check("ambient with only chew on: picks chew",
          dog.state == State.CHEWING, f"state={dog.state.name}")
    set_all(True)


@step(100)
def t_stretch_switch():
    reset_dog()
    dog.settings.set("timed.stretch_reminders", False)
    dog.stretch_pending = True
    dog._check_pending()
    off_ok = dog.state == State.SLEEPING and not dog.stretch_pending
    dog.settings.set("timed.stretch_reminders", True)
    dog.stretch_pending = True
    dog._check_pending()
    on_ok = dog.state == State.STRETCHING
    check("stretch reminder honors its switch", off_ok and on_ok)
    reset_dog()


@step(100)
def t_water_switch():
    dog.settings.set("timed.water_reminders", False)
    dog.water_pending = True
    dog._check_pending()
    off_ok = dog.state == State.SLEEPING and not dog.water_pending
    dog.settings.set("timed.water_reminders", True)
    dog.water_pending = True
    dog._check_pending()
    on_ok = dog.state == State.DRINKING
    check("water reminder honors its switch", off_ok and on_ok)
    reset_dog()


@step(100)
def t_cursor_alert_off():
    dog.settings.set("interactive.cursor_alert", False)
    cursor_near_dog()


@step(1200)
def t_cursor_alert_off_check():
    check("cursor alert off: cursor near does nothing",
          dog.state == State.SLEEPING, f"state={dog.state.name}")
    dog.settings.set("interactive.cursor_alert", True)
    # leave the cursor near: next step expects ALERT


@step(1200)
def t_cursor_alert_on_check():
    check("cursor alert on: cursor near -> ALERT",
          dog.state == State.ALERT, f"state={dog.state.name}")
    cursor_far()
    reset_dog()


@step(100)
def t_click_excited_switch():
    dog.settings.set("interactive.excited_on_click", False)
    left_click(dog.dog_sx, WIN_H - 30)
    off_ok = dog.state == State.SLEEPING
    dog.settings.set("interactive.excited_on_click", True)
    left_click(dog.dog_sx, WIN_H - 30)
    on_ok = dog.state == State.EXCITED
    check("click-excited honors its switch", off_ok and on_ok)
    reset_dog()


@step(100)
def t_fetch_switch():
    dog.settings.set("interactive.fetch_ball", False)
    left_click(dog.ball_cx, WIN_H - 10)
    # NB: with fetch off, the click falls through to the dog branch -> EXCITED
    off_ok = dog.state != State.FETCHING and abs(dog.ball_x - dog.ball_cx) < 5
    reset_dog()
    dog.settings.set("interactive.fetch_ball", True)
    left_click(dog.ball_cx, WIN_H - 10)
    on_ok = dog.state == State.FETCHING
    check("ball-fetch honors its switch", off_ok and on_ok)
    reset_dog()


@step(100)
def t_fidgets_off_start():
    dog.settings.set("idle.fidgets_lying", False)
    dog.fidgets.rate_mult = 30.0            # would fire every ~0.2s if allowed
    dog.fidgets._gap_ticks = 1
    t_fidgets_off_start.seen = False

    poll = QTimer(dog)
    poll.timeout.connect(
        lambda: setattr(t_fidgets_off_start, "seen",
                        t_fidgets_off_start.seen or dog.fidgets.active is not None))
    poll.start(30)
    t_fidgets_off_start.poll = poll


@step(4000)
def t_fidgets_off_check():
    t_fidgets_off_start.poll.stop()
    check("fidgets (lying) off: none fire in 4s at 30x rate",
          not t_fidgets_off_start.seen)
    dog.settings.set("idle.fidgets_lying", True)
    dog.fidgets._gap_ticks = 1


@step(3000)
def t_fidgets_on_check():
    seen = dog.fidgets.active is not None or len(dog.fidgets._history) > 0
    check("fidgets (lying) on: they fire again", seen)
    reset_dog()


@step(100)
def t_test_bypasses_switch():
    dog.settings.set("idle.scratch", False)
    dog._test_scratch()
    check("Test menu force-fires with switch off",
          dog.state == State.SCRATCHING, f"state={dog.state.name}")
    dog.settings.set("idle.scratch", True)
    reset_dog()


@step(100)
def t_menu_structure():
    menu = dog._build_menu()
    subs = {a.menu().title(): a.menu() for a in menu.actions()
            if a.menu() is not None}
    grouped_ok = set(subs) == {"Idle", "Timed", "Interactive", "Command"}
    counts_ok = (len(subs.get("Idle", QMenu()).actions()) == 6
                 and len(subs.get("Timed", QMenu()).actions()) == 2
                 and len(subs.get("Interactive", QMenu()).actions()) == 3
                 and len(subs.get("Command", QMenu()).actions()) == 1)
    all_actions = [a for m in subs.values() for a in m.actions()]
    checkable_ok = all(a.isCheckable() for a in all_actions)
    # checked state must mirror the store
    dog.settings.set("idle.chew", False)
    menu2 = dog._build_menu()
    idle2 = next(a.menu() for a in menu2.actions()
                 if a.menu() is not None and a.menu().title() == "Idle")
    chew_action = next(a for a in idle2.actions() if a.text() == "Chew bone")
    mirror_ok = chew_action.isChecked() is False
    dog.settings.set("idle.chew", True)
    test_labels = [a.text() for a in menu.actions() if a.text().startswith("Test:")]
    test_ok = len(test_labels) == 7
    check("menu: grouped checkable toggles mirror the store + Test intact",
          grouped_ok and counts_ok and checkable_ok and mirror_ok and test_ok,
          f"groups={sorted(subs)} tests={len(test_labels)}")


def finish():
    log("")
    if _failures:
        log("FAILURES:")
        for f in _failures:
            log(f"  - {f}")
    else:
        log("ALL CHECKS PASSED")
    with open(os.path.join(OUT, "phase2-log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    app.exit(1 if _failures else 0)


run_steps()
sys.exit(app.exec_())
