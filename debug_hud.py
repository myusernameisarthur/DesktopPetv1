"""Development debug HUD for Biscuit.

A small, non-interactive, click-through text box that floats just above the dog
and reports the live state machine. This is a DEV OBSERVATION TOOL — it is fully
self-contained in this module. To remove it entirely, delete this file and the
three clearly-marked `# === DEBUG HUD ===` blocks in biscuit.py.

It reads everything from the live Biscuit instance via public attributes; it does
not change any behavior, timing, or art. It runs off the host app's existing
33 ms tick (Biscuit calls `refresh(self)` once per frame) — no extra timer.
"""

import math
import time
import ctypes

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QFontMetrics


_TWO_PI = 2.0 * math.pi

# Win32  extended styles used to force OS-level click-through as a belt-and-braces
# backup to Qt.WindowTransparentForInput.
_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020


def _cycle_pct(value):
    """Position within a sine cycle (0-100%) for a continuously growing phase."""
    return int((value % _TWO_PI) / _TWO_PI * 100)


def hud_phase(dog):
    """Human-readable 'where are we in the current animation' string.

    Pulled from the same real values the painter uses, so it can't drift from
    what's actually on screen.
    """
    n = dog.state.name
    tf = getattr(dog, "task_frames", 0)
    sf = getattr(dog, "state_frames", 0)
    tp = getattr(dog, "task_phase", 0)

    if n == "SLEEPING":
        return f"breath {_cycle_pct(dog.breath_phase)}%"
    if n == "ALERT":
        return "holding"
    if n == "EXCITED":
        return f"{max(0, min(100, int((1 - sf / 75.0) * 100)))}% done"
    if n == "STRETCHING":
        return f"{int(min(tf, 90) / 90.0 * 100)}% done"
    if n in ("SCRATCHING", "CHEWING"):
        return f"{int(min(tf, sf) / sf * 100)}% done" if sf else "..."
    if n == "DRINKING":
        if tp == 0:
            return f"approach {_cycle_pct(dog.walk_phase)}%"
        dur = 80 if getattr(dog, "bowl_full", False) else 30
        return f"drink {int(min(tf, dur) / dur * 100)}%"
    if n == "FETCHING":
        return f"step {_cycle_pct(dog.walk_phase)}%" if tp == 0 else "pickup"
    if n == "SNIFF_WALK":
        return f"step {_cycle_pct(dog.walk_phase)}%" if tp == 0 else "sniff-pause"
    if n in ("WALKING", "RETURNING_BALL", "TASK_RETURN"):
        return f"step {_cycle_pct(dog.walk_phase)}%"
    return "-"


def hud_next(dog):
    """Soonest upcoming scheduled behavior + countdown, from the live QTimers.

    QTimer.remainingTime() returns ms, or -1 when the timer is inactive (e.g. the
    sleep/ambient timer is stopped while a task runs).
    """
    cands = []
    for label, attr in (("wander", "_sleep_timer"),
                        ("stretch", "_stretch_timer"),
                        ("water", "_water_timer")):
        timer = getattr(dog, attr, None)
        if timer is None:
            continue
        rt = timer.remainingTime()
        if rt is not None and rt >= 0:
            cands.append((rt, label))
    if not cands:
        return "(none active)"
    rt, label = min(cands)
    return f"{label} {rt / 1000.0:.0f}s"


class DebugHUD(QWidget):
    """Floating, click-through state read-out. Created and driven by Biscuit."""

    _GAP_ABOVE_DOG = 56   # px above tb_top; clears the tallest (standing) pose

    def __init__(self, dog):
        super().__init__()
        self._dog = dog
        self._lines = []
        self._last_state = None
        self._t0 = time.monotonic()

        # Fonts + a fully metrics-driven layout so nothing clips or overlaps at
        # any system DPI (the app runs without high-DPI scaling, so point sizes
        # render larger on high-DPI screens — measure, don't hard-code).
        self._label_font = QFont("Consolas", 8)
        self._label_font.setStyleHint(QFont.Monospace)
        self._value_font = QFont("Consolas", 8, QFont.Bold)
        self._value_font.setStyleHint(QFont.Monospace)
        fm_l = QFontMetrics(self._label_font)
        fm_v = QFontMetrics(self._value_font)

        self._pad = 9
        self._x_label = self._pad
        self._x_value = self._x_label + fm_l.horizontalAdvance("M" * 8)
        self._line_h = fm_l.height() + 3
        self._y0 = self._pad + fm_l.ascent()
        # Widest realistic value is the longest state name.
        widest_val = fm_v.horizontalAdvance("RETURNING_BALL")
        w = self._x_value + widest_val + self._pad
        h = self._y0 + self._line_h * 5 + fm_l.descent() + self._pad
        self.setFixedSize(w, h)
        # Click-through at the Qt level: the whole window ignores mouse input, so
        # it can never capture a click or interfere with the dog's mask-based
        # click-through. (This is the *correct* use of TransparentForInput — the
        # HUD is purely a read-out, unlike the interactive dog window.)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # Click-through is provided by the Qt.WindowTransparentForInput flag above
        # plus the Win32 WS_EX_TRANSPARENT applied in showEvent.

        self._reposition()

    # ── lifecycle ────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_win32_clickthrough()

    def _apply_win32_clickthrough(self):
        """OS-level backup for click-through (WS_EX_TRANSPARENT | WS_EX_LAYERED)."""
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            ex = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
            user32.SetWindowLongW(
                hwnd, _GWL_EXSTYLE, ex | _WS_EX_LAYERED | _WS_EX_TRANSPARENT)
        except Exception:
            pass  # dev tool: never let HUD setup break the app

    # ── per-frame update (called from Biscuit._on_tick) ──────────────────────

    def refresh(self, dog):
        # Track time-in-state ourselves so biscuit.py needs no instrumentation.
        if dog.state != self._last_state:
            self._last_state = dog.state
            self._t0 = time.monotonic()
        secs = time.monotonic() - self._t0

        self._lines = [
            ("STATE", dog.state.name),
            ("ANIM", dog.current_anim()),
            ("PHASE", hud_phase(dog)),
            ("FACING", "left" if dog.facing < 0 else "right"),
            ("t/state", f"{secs:4.1f}s"),
            ("next", hud_next(dog)),
        ]
        self._reposition()
        self.update()

    def _reposition(self):
        """Follow the dog horizontally; fixed height above the taskbar.

        Clamped so the box never clips off the top or the left/right edges.
        """
        dog = self._dog
        scr_w = getattr(dog, "sw", 1920)
        tb_top = getattr(dog, "tb_top", 1000)
        dog_x = int(getattr(dog, "dog_sx", scr_w // 2))  # screen x == window-local x
        w, h = self.width(), self.height()

        x = dog_x - w // 2
        x = max(2, min(scr_w - w - 2, x))
        y = max(2, tb_top - self._GAP_ABOVE_DOG - h)
        self.move(x, y)

    # ── paint ────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Semi-transparent dark panel with a subtle border.
        p.setPen(QPen(QColor(120, 200, 140, 110), 1))
        p.setBrush(QColor(14, 16, 20, 205))
        p.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 6, 6)

        y = self._y0
        for label, value in self._lines:
            p.setFont(self._label_font)
            p.setPen(QColor(120, 150, 130))
            p.drawText(self._x_label, y, label)
            p.setFont(self._value_font)
            p.setPen(QColor(200, 235, 205))
            p.drawText(self._x_value, y, str(value))
            y += self._line_h
        p.end()
