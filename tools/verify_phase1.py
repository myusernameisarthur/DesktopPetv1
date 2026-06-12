"""Phase 1 verification harness (dev tool — not part of the app).

Drives the REAL Biscuit app:
  A. Force-fires every lying and standing fidget and captures a screenshot of
     each mid-fidget (saved to verify/phase1/).
  B. Probes click-through with Win32 WindowFromPoint: a point on the dog must
     hit the overlay; a point on the bare strip away from the dog must not.
  C. Accelerated idle soak (rate_mult) in both poses, logging every fidget the
     engine picks naturally, to check variety / irregular gaps / no-repeat.
  D. Measures idle CPU (process_time over wall time).

Writes verify/phase1/phase1-log.txt and exits with 0 on success.
Run: python tools/verify_phase1.py
"""

import os
import sys
import time
import ctypes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "verify", "phase1")
os.makedirs(OUT, exist_ok=True)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)

import biscuit
from biscuit import State
from fidgets import LYING_FIDGETS, STANDING_FIDGETS, ActiveFidget

dog = biscuit.Biscuit()
dog._greet_timer.stop()      # keep the launch greet out of this harness

log_lines = []


def log(msg):
    print(msg, flush=True)
    log_lines.append(msg)


def set_cursor(x, y):
    ctypes.windll.user32.SetCursorPos(int(x), int(y))


def cursor_far():
    set_cursor(dog.sw // 2, 80)        # top of screen, far from the dog


def cursor_near_dog():
    set_cursor(int(dog.dog_sx) + 60, dog.tb_top - 25)


def shot(name):
    """Capture the dog + HUD region of the real screen."""
    screen = QApplication.primaryScreen()
    x = max(0, int(dog.dog_sx) - 160)
    y = max(0, dog.tb_top - 230)
    pm = screen.grabWindow(0, x, y, 340, 240)
    path = os.path.join(OUT, name + ".png")
    pm.save(path)
    log(f"  shot -> verify/phase1/{name}.png")


def hwnd_at(x, y):
    pt = ctypes.wintypes.POINT(int(x), int(y))
    return ctypes.windll.user32.WindowFromPoint(pt)


# ── step runner: (delay_ms_after_previous, callback) ────────────────────────

_steps = []
_failures = []


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


# ── A. force-fire every fidget + screenshot ──────────────────────────────────

def inject_and_shoot(spec, pose_label):
    """Set the fidget active directly, then screenshot at its midpoint."""
    dog.fidgets._gap_ticks = 10 ** 9          # no natural starts during tests
    dog.fidgets.active = ActiveFidget(spec)
    mid_ms = int(spec.duration_s * 500)

    def take():
        fa = dog.fidgets.active
        ok = fa is not None and fa.name == spec.name
        log(f"[{pose_label}] {spec.name}: active-at-midpoint={ok} "
            f"state={dog.state.name}")
        if not ok:
            _failures.append(f"{spec.name} not active at midpoint")
        shot(f"{pose_label}-{spec.name}")
    QTimer.singleShot(max(60, mid_ms), take)


def build_fidget_steps():
    @step(500)
    def baseline():
        cursor_far()
        log(f"start: state={dog.state.name} (expect SLEEPING)")

    @step(800)
    def baseline_shot():
        shot("lying-baseline")

    for spec in LYING_FIDGETS:
        def make(s=spec):
            @step(int(s.duration_s * 1000) + 700)
            def fire():
                if dog.state != State.SLEEPING:
                    _failures.append(f"not SLEEPING before {s.name}")
                inject_and_shoot(s, "lying")
        make()

    @step(1500)
    def go_alert():
        cursor_near_dog()
        log("cursor moved near dog (expect ALERT)")

    @step(800)
    def alert_shot():
        log(f"state={dog.state.name} (expect ALERT)")
        if dog.state != State.ALERT:
            _failures.append("cursor proximity did not produce ALERT")
        shot("standing-alert-baseline")

    for spec in STANDING_FIDGETS:
        def make(s=spec):
            @step(int(s.duration_s * 1000) + 700)
            def fire():
                cursor_near_dog()             # keep ALERT alive
                if dog.state != State.ALERT:
                    _failures.append(f"not ALERT before {s.name}")
                inject_and_shoot(s, "standing")
        make()


# ── B. click-through probes ──────────────────────────────────────────────────

def build_clickthrough_steps():
    @step(2500)
    def probe():
        cursor_far()                          # let ALERT settle off later; probe now
        our = int(dog.winId())
        hud = int(dog._hud.winId()) if dog._hud is not None else 0
        # On the dog (it is ALERT/standing or SLEEPING; both footprints overlap
        # near the body center just above the taskbar)
        on_dog = hwnd_at(dog.dog_sx, dog.tb_top - 15)
        # Inside the overlay strip but far from dog and decor
        empty_x = (dog.walk_min + dog.bed_cx) / 2 - 100
        on_empty = hwnd_at(empty_x, dog.tb_top - 10)
        # Where the HUD sits
        hud_pt = hwnd_at(dog._hud.x() + 10, dog._hud.y() + 10) if hud else 0

        dog_ok = on_dog == our
        empty_ok = on_empty != our
        hud_ok = hud_pt != hud
        log(f"click-through: on-dog-hits-overlay={dog_ok} "
            f"empty-strip-passes-through={empty_ok} hud-passes-through={hud_ok}")
        if not dog_ok:
            _failures.append("point on dog does not hit overlay")
        if not empty_ok:
            _failures.append("empty strip point hits overlay (mask broken)")
        if not hud_ok:
            _failures.append("HUD captures input")


# ── C. accelerated idle soak ─────────────────────────────────────────────────

soak_events = []          # (t, pose, name)
_soak_last_id = [None]
_soak_pose = ["lying"]


def poll_soak():
    fa = dog.fidgets.active
    if fa is not None and id(fa) != _soak_last_id[0]:
        _soak_last_id[0] = id(fa)
        soak_events.append((time.monotonic(), _soak_pose[0], fa.name))


def build_soak_steps():
    poller = QTimer()
    poller.timeout.connect(poll_soak)

    @step(500)
    def start_soak():
        cursor_far()
        dog.fidgets.rate_mult = 6.0           # gaps 4-12s -> ~0.7-2s
        dog.fidgets._gap_ticks = 30
        _soak_pose[0] = "lying"
        poller.start(40)
        log("soak: lying, 45s at rate_mult=6")

    @step(45_000)
    def to_standing():
        _soak_pose[0] = "standing"
        cursor_near_dog()
        log("soak: standing (ALERT), 30s")

    @step(30_000)
    def end_soak():
        poller.stop()
        dog.fidgets.rate_mult = 1.0
        cursor_far()
        analyse_soak()


def analyse_soak():
    lying = [e for e in soak_events if e[1] == "lying"]
    standing = [e for e in soak_events if e[1] == "standing"]
    log(f"soak events: lying={len(lying)} standing={len(standing)}")
    for label, ev in (("lying", lying), ("standing", standing)):
        names = [n for _, _, n in ev]
        log(f"  {label} sequence: {' '.join(names)}")
        distinct = len(set(names))
        log(f"  {label}: distinct={distinct}")
        repeats = sum(1 for a, b in zip(names, names[1:]) if a == b)
        if repeats:
            _failures.append(f"{label}: {repeats} back-to-back repeats")
        if len(ev) >= 3:
            gaps = [round(b[0] - a[0], 2) for a, b in zip(ev, ev[1:])]
            log(f"  {label} gaps(s): {gaps}")
            if len(set(gaps)) == 1:
                _failures.append(f"{label}: metronome gaps")
        if distinct < 4:
            _failures.append(f"{label}: only {distinct} distinct fidgets")


# ── D. idle CPU ──────────────────────────────────────────────────────────────

_cpu0 = [0.0, 0.0]


def build_cpu_steps():
    @step(1000)
    def cpu_start():
        _cpu0[0] = time.process_time()
        _cpu0[1] = time.monotonic()

    @step(10_000)
    def cpu_end():
        cpu = time.process_time() - _cpu0[0]
        wall = time.monotonic() - _cpu0[1]
        pct = cpu / wall * 100
        log(f"idle CPU over {wall:.1f}s: {pct:.1f}% of one core")
        if pct > 25:
            _failures.append(f"idle CPU too high: {pct:.1f}%")


def finish():
    log("")
    if _failures:
        log("FAILURES:")
        for f in _failures:
            log(f"  - {f}")
    else:
        log("ALL CHECKS PASSED")
    with open(os.path.join(OUT, "phase1-log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    app.exit(1 if _failures else 0)


import ctypes.wintypes  # noqa: E402  (used by hwnd_at)

build_fidget_steps()
build_clickthrough_steps()
build_soak_steps()
build_cpu_steps()
run_steps()
sys.exit(app.exec_())
