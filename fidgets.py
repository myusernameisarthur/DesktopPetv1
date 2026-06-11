"""Idle micro-behavior (fidget) engine for Biscuit/Persi.

A fidget is a short, small motion that plays WITHOUT changing the state machine:
the dog stays SLEEPING but its ear flicks. The engine only decides WHICH fidget
is active and how far along it is; the drawing code in biscuit.py reads the
active fidget and applies a small additive delta to the base pose.

Mechanics (per docs/persi-behavior-animation-map.md Part 2):
- Irregular timing: gaps between fidgets are rolled uniformly from a range
  (4-12 s lying, 3-8 s standing/alert), never a fixed beat.
- Weighting: common / medium / rare via integer weights.
- No-repeat memory: the last 2 fidgets are excluded from the next draw.
- Per-fidget cooldown: each fidget also carries its own re-use cooldown.
- One fidget at a time; a fidget is cancelled instantly if the pose/state
  changes, and never starts outside an idle pose (so it can never touch a
  locked one-shot like stretch or scratch).
- rate_mult is the single hook for future modulators (energy, time of day);
  >1.0 means more frequent fidgets. Out of scope for v1, default 1.0.
"""

import random

TICK_MS = 33
TPS = 1000.0 / TICK_MS          # ticks per second (~30)

POSE_LYING = "lying"
POSE_STANDING = "standing"


class FidgetSpec:
    __slots__ = ("name", "duration_s", "weight", "cooldown_s")

    def __init__(self, name, duration_s, weight, cooldown_s):
        self.name = name
        self.duration_s = duration_s
        self.weight = weight          # common=6, medium=3, rare=1
        self.cooldown_s = cooldown_s  # min seconds before this one can replay


# Catalog per docs/persi-behavior-animation-map.md Part 1 (+ the three folded
# in from the roadmap: stress shake-off, bone-from-pocket chew, lying scratch).
LYING_FIDGETS = [
    FidgetSpec("ear-flick",   0.30, 6, 8),
    FidgetSpec("nose-twitch", 0.25, 6, 8),
    FidgetSpec("tail-twitch", 0.30, 6, 8),
    FidgetSpec("sigh",        1.20, 3, 20),
    FidgetSpec("dream-kick",  0.60, 3, 20),
    FidgetSpec("eye-crack",   0.50, 3, 20),
    FidgetSpec("resettle",    1.00, 1, 45),
    FidgetSpec("scratch",     1.20, 1, 45),
]

STANDING_FIDGETS = [
    FidgetSpec("blink",        0.20, 6, 4),
    FidgetSpec("ear-swivel",   0.40, 6, 8),
    FidgetSpec("weight-shift", 0.50, 6, 8),
    FidgetSpec("head-tilt",    0.80, 3, 15),
    FidgetSpec("look-around",  1.00, 3, 15),
    FidgetSpec("wag-burst",    0.70, 3, 15),
    FidgetSpec("shake-off",    0.80, 1, 40),
    FidgetSpec("bone-chew",    3.00, 1, 60),
    FidgetSpec("sit",          2.00, 1, 60),
]

_CATALOG = {POSE_LYING: LYING_FIDGETS, POSE_STANDING: STANDING_FIDGETS}

# Gap until the next fidget attempt, per pose. Standing (= ALERT, cursor near)
# fidgets a little more often as part of ALERT's own idle signature.
_GAP_RANGE_S = {POSE_LYING: (4.0, 12.0), POSE_STANDING: (3.0, 8.0)}


class ActiveFidget:
    __slots__ = ("spec", "ticks", "total")

    def __init__(self, spec):
        self.spec = spec
        self.ticks = 0
        self.total = max(1, int(spec.duration_s * TPS))

    @property
    def name(self):
        return self.spec.name

    @property
    def progress(self):
        return min(1.0, self.ticks / self.total)

    @property
    def remaining_s(self):
        return max(0.0, (self.total - self.ticks) / TPS)


class FidgetEngine:
    def __init__(self):
        self.rate_mult = 1.0     # future modulator hook; 1.0 = design rates
        self.active = None
        self._history = []       # last 2 fidget names (no-repeat memory)
        self._cooldowns = {}     # name -> ticks until reusable
        self._pose = None
        self._gap_ticks = self._roll_gap(POSE_LYING)

    # ── per-tick drive (called from Biscuit._on_tick) ────────────────────────

    def tick(self, pose):
        """Advance one tick. pose is POSE_LYING / POSE_STANDING, or None when
        the dog is not in a fidget-eligible idle state (or is paused)."""
        for name in list(self._cooldowns):
            self._cooldowns[name] -= 1
            if self._cooldowns[name] <= 0:
                del self._cooldowns[name]

        if pose != self._pose:
            # State change: drop any in-flight fidget and re-roll the gap so
            # the new pose doesn't fidget the instant it's entered.
            self.cancel()
            self._pose = pose
            if pose is not None:
                self._gap_ticks = self._roll_gap(pose)

        if pose is None:
            return

        if self.active is not None:
            self.active.ticks += 1
            if self.active.ticks >= self.active.total:
                self._finish()
            return

        self._gap_ticks -= 1
        if self._gap_ticks <= 0:
            self._start(pose)
            if self.active is None:
                self._gap_ticks = int(TPS)   # nothing eligible; retry in ~1 s

    # ── internals ────────────────────────────────────────────────────────────

    def _roll_gap(self, pose):
        lo, hi = _GAP_RANGE_S[pose]
        mult = self.rate_mult if self.rate_mult > 0 else 1.0
        return max(1, int(random.uniform(lo, hi) / mult * TPS))

    def _start(self, pose):
        recent = set(self._history)
        eligible = [f for f in _CATALOG[pose]
                    if f.name not in recent and f.name not in self._cooldowns]
        if not eligible:
            return
        total = sum(f.weight for f in eligible)
        r = random.uniform(0.0, total)
        for spec in eligible:
            r -= spec.weight
            if r <= 0:
                break
        self.active = ActiveFidget(spec)

    def _finish(self):
        spec = self.active.spec
        self.active = None
        self._history.append(spec.name)
        del self._history[:-2]
        self._cooldowns[spec.name] = int(spec.cooldown_s * TPS)
        self._gap_ticks = self._roll_gap(self._pose)

    def cancel(self):
        self.active = None
