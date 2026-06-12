"""Mouse-gesture recognition for Biscuit/Persi commands.

Phase 4a enabler: pure math on the cursor position the app already polls each
tick — no OS hooks, no listeners. Currently one gesture: the roll-over circle
(click the dog, then circle the cursor around it about three times).

How it works: while armed, each tick we take the cursor's angle around the
dog's center and accumulate the signed change. Circling consistently in one
direction grows |accumulated| toward LOOPS_NEEDED * 2π; jitter and reversals
cancel out, so only a deliberate, consistent circling motion completes. The
recognizer disarms on timeout or if the cursor stays out of the ring too long.
"""

import math

TWO_PI = 2.0 * math.pi


class CircleGestureRecognizer:
    LOOPS_NEEDED = 3.0      # full turns required (~3 x 360°)
    WINDOW_TICKS = 240      # arming window (~11 s at the app's effective rate)
    R_MIN = 25.0            # ring around the dog the cursor must stay inside
    R_MAX = 220.0
    OFF_RING_GRACE = 40     # ticks the cursor may spend outside the ring
    MAX_STEP = math.pi / 2  # per-tick angle jumps above this are ignored

    def __init__(self):
        self.armed = False
        self._accum = 0.0
        self._last_ang = None
        self._ticks_left = 0
        self._grace = 0

    # ── public state (read by the HUD) ───────────────────────────────────────

    @property
    def loops(self):
        return abs(self._accum) / TWO_PI

    @property
    def seconds_left(self):
        return self._ticks_left * 0.047    # effective ~21 Hz tick

    def arm(self):
        """Start watching. Called when the dog is clicked."""
        self.armed = True
        self._accum = 0.0
        self._last_ang = None
        self._ticks_left = self.WINDOW_TICKS
        self._grace = self.OFF_RING_GRACE

    def disarm(self):
        self.armed = False
        self._accum = 0.0
        self._last_ang = None

    def tick(self, center_x, center_y, cur_x, cur_y):
        """Advance one tick. Returns True exactly once, when the gesture
        completes; the recognizer disarms itself either way."""
        if not self.armed:
            return False

        self._ticks_left -= 1
        if self._ticks_left <= 0:
            self.disarm()
            return False

        dx = cur_x - center_x
        dy = cur_y - center_y
        r = math.hypot(dx, dy)
        if r < self.R_MIN or r > self.R_MAX:
            self._grace -= 1
            self._last_ang = None          # don't bridge across an exit
            if self._grace <= 0:
                self.disarm()
            return False
        self._grace = self.OFF_RING_GRACE

        ang = math.atan2(dy, dx)
        if self._last_ang is not None:
            d = ang - self._last_ang
            while d > math.pi:
                d -= TWO_PI
            while d < -math.pi:
                d += TWO_PI
            if abs(d) < self.MAX_STEP:     # ignore teleport-sized jumps
                self._accum += d
        self._last_ang = ang

        if abs(self._accum) >= self.LOOPS_NEEDED * TWO_PI:
            self.disarm()
            return True
        return False
