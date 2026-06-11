"""Phase 3 verification harness (dev tool — not part of the app).

Forces each locomotion state on the REAL app and measures, over ~2 s each:
  - actual travel speed (px/s) vs the gait's authored speed,
  - the walk_phase advance rate vs the gait's phase_rate,
  - the ANIM label the HUD reports,
and captures a mid-stride screenshot per gait. Also confirms the sniff-walk
still pause-and-goes, and that the four gaits' measured speeds are distinct
and correctly ordered (scamper > brisk > plod > sniff).

Writes verify/phase3/phase3-log.txt; exit code 0 on success.
Run: python tools/verify_phase3.py
"""

import os
import sys
import time
import ctypes
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "verify", "phase3")
os.makedirs(OUT, exist_ok=True)

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="persi-verify-")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)

import biscuit
from biscuit import State, GAITS

dog = biscuit.Biscuit()
TPS = 1000.0 / 33.0

log_lines = []
_failures = []
measured = {}      # anim label -> px/s


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
    dog.dog_sx = float(dog.bed_cx)
    dog.ball_x = float(dog.ball_cx)
    dog.ball_visible = True
    dog.fidgets.cancel()
    dog._sleep_timer.stop()


def shot(name):
    screen = QApplication.primaryScreen()
    x = max(0, int(dog.dog_sx) - 170)
    y = max(0, dog.tb_top - 230)
    pm = screen.grabWindow(0, x, y, 340, 240)
    pm.save(os.path.join(OUT, name + ".png"))


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


# ── gait measurement ─────────────────────────────────────────────────────────

class Probe:
    """Measures in per-tick units (what gaits are authored in), via the app's
    own tick counter — Windows timer coalescing makes the 33 ms QTimer fire at
    ~47 ms on this machine (~21 ticks/s), so wall-clock units would skew."""

    def __init__(self):
        self.x0 = self.wp0 = self.ticks0 = None

    def begin(self):
        self.x0 = dog.dog_sx
        self.wp0 = dog.walk_phase
        self.ticks0 = dog._ticks

    def end(self):
        dticks = max(1, dog._ticks - self.ticks0)
        dx = abs(dog.dog_sx - self.x0)
        dwp = dog.walk_phase - self.wp0
        return dx / dticks, dwp / dticks   # px/tick, phase/tick


probe = Probe()


def gait_test(label, setup, expect_anim, gait_name, expect_travel=True):
    """Queue: setup -> wait 300ms -> begin probe -> 1.6s -> screenshot+check."""
    @step(300)
    def s_setup():
        reset_dog()
        cursor_far()
        setup()

    @step(300)
    def s_begin():
        probe.begin()

    @step(1100)
    def s_shot():
        shot(f"gait-{expect_anim}")

    @step(500)
    def s_check():
        px_t, ppt = probe.end()
        g = GAITS[gait_name]
        anim_ok = dog.current_anim() == expect_anim
        if expect_travel:
            speed_ok = abs(px_t - g.speed) / g.speed < 0.15
            phase_ok = abs(ppt - g.phase_rate) < 0.03
            measured[expect_anim] = px_t
            check(f"{label}: anim+speed+phase",
                  anim_ok and speed_ok and phase_ok,
                  f"anim={dog.current_anim()} speed={px_t:.2f}px/tick "
                  f"(expect {g.speed}) phase/tick={ppt:.2f} (expect {g.phase_rate})")
        else:
            check(f"{label}: anim label", anim_ok, f"anim={dog.current_anim()}")


# WALKING — brisk trot
def setup_walking():
    dog.state = State.WALKING
    dog.walk_dir = -1
    dog.facing = -1
    dog.state_frames = 10_000


gait_test("WALKING roam", setup_walking, "trot-brisk", "trot-brisk")


# TASK_RETURN — plod
def setup_task_return():
    dog.dog_sx = float(dog.bed_cx - 300)
    dog.state = State.TASK_RETURN


gait_test("TASK_RETURN home", setup_task_return, "plod", "plod")


# RETURNING_BALL — plod (carry)
def setup_returning_ball():
    dog.dog_sx = float(dog.bed_cx - 300)
    dog.ball_visible = False
    dog.state = State.RETURNING_BALL


gait_test("RETURNING_BALL home", setup_returning_ball, "plod-carry", "plod")


# FETCHING — scamper
def setup_fetching():
    dog.dog_sx = float(dog.bed_cx)
    dog.ball_x = float(dog.bed_cx - 450)
    dog.ball_visible = True
    dog.state = State.FETCHING
    dog.task_phase = 0


gait_test("FETCHING ball", setup_fetching, "scamper", "scamper")


# SNIFF_WALK — sniff-walk + pause-and-go
def setup_sniff():
    dog._test_sniff()
    dog.sniff_dest = max(dog.walk_min, dog.dog_sx - 600)
    dog.sniff_next_pause = dog.dog_sx - 350      # no pause inside the probe window


gait_test("SNIFF_WALK", setup_sniff, "sniff-walk", "sniff-walk")


@step(300)
def t_sniff_pauses():
    reset_dog()
    dog._test_sniff()
    t_sniff_pauses.seen = False
    poll = QTimer(dog)
    poll.timeout.connect(
        lambda: setattr(t_sniff_pauses, "seen",
                        t_sniff_pauses.seen
                        or (dog.state == State.SNIFF_WALK and dog.task_phase == 1)))
    poll.start(25)
    t_sniff_pauses.poll = poll


@step(3500)
def t_sniff_pauses_check():
    t_sniff_pauses.poll.stop()
    check("sniff-walk pause-and-go intact", t_sniff_pauses.seen)
    reset_dog()


@step(200)
def t_distinct():
    s = measured
    ok = (s.get("scamper", 0) > s.get("trot-brisk", 0)
          > s.get("plod", 0) > s.get("sniff-walk", 0))
    check("gaits ordered scamper > brisk > plod > sniff",
          ok, " ".join(f"{k}={v:.0f}" for k, v in s.items()))


@step(200)
def t_return_to_sleep():
    # End-to-end: a forced TASK_RETURN must finish back at SLEEPING on the bed
    reset_dog()
    dog.dog_sx = float(dog.bed_cx - 60)
    dog.state = State.TASK_RETURN


@step(4000)
def t_return_to_sleep_check():
    check("TASK_RETURN completes back to SLEEPING",
          dog.state == State.SLEEPING and abs(dog.dog_sx - dog.bed_cx) < 3,
          f"state={dog.state.name}")


def finish():
    log("")
    if _failures:
        log("FAILURES:")
        for f in _failures:
            log(f"  - {f}")
    else:
        log("ALL CHECKS PASSED")
    with open(os.path.join(OUT, "phase3-log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    app.exit(1 if _failures else 0)


run_steps()
sys.exit(app.exec_())
