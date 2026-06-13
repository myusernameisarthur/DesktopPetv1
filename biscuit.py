import sys
import math
import random
import ctypes
import winreg
import os
import time
from ctypes import wintypes
from enum import Enum

from PyQt5.QtWidgets import (QApplication, QWidget, QMenu, QAction,
                             QActionGroup)
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import (QPainter, QColor, QBrush, QPen, QRegion,
                         QPainterPath, QFont, QCursor)

from fidgets import FidgetEngine, POSE_LYING, POSE_STANDING
from gestures import CircleGestureRecognizer
from settings import Settings

try:
    from sprites import SpriteSet, available_kits
except Exception:           # missing module/assets must never kill the app
    SpriteSet = None

    def available_kits():
        return {}


class State(Enum):
    SLEEPING = 0
    ALERT = 1
    WALKING = 2
    EXCITED = 3
    FETCHING = 4        # walking to thrown ball
    RETURNING_BALL = 5  # carrying ball back to corner
    STRETCHING = 6      # stretch-reminder animation
    DRINKING = 7        # water-reminder: walk to bowl + drink
    TASK_RETURN = 8     # walking back to bed after a task
    SCRATCHING = 9      # idle: back-leg scratch at ear
    CHEWING = 10        # idle: gnaw a bone
    SNIFF_WALK = 11     # idle: slow walk with nose-down pauses
    ROLL_OVER = 12      # command: circle gesture -> on back, paws up, wriggle
    BARKING = 13        # reactive: short head-back bark (greet flourish; 4c later)
    BEG = 14            # command: double-click -> sit up, front paws raised
    GREETING = 15       # reactive: launch / return from long idle -> hops + wag
    ZOOMIES = 16        # idle (rare): fast back-and-forth dashes
    CLIMBING = 17       # startup: hauls up from behind the taskbar ledge


# Single source of truth: the animation each state actually renders.
# Names describe the real motion (see _draw / _draw_standing / _draw_sleeping),
# NOT the behavior's purpose. Locomotion states are routed through GAITS below,
# so the label names the gait.
ANIMATION = {
    State.SLEEPING:       "breathing",    # _draw_sleeping, breath_phase swell
    State.ALERT:          "alert-stand",  # _draw_standing, ears up, gentle sway
    State.WALKING:        "trot-brisk",   # even, perky roam
    State.EXCITED:        "bounce",       # vertical bounce_val + tongue + wag
    State.FETCHING:       "scamper",      # fast, bouncy, short strides
    State.RETURNING_BALL: "plod-carry",   # heavy heading-home walk + ball at mouth
    State.STRETCHING:     "stretch",      # _draw_sleeping + stretch_factor + yawn
    State.DRINKING:       "drink",        # brisk trot to bowl, then head-bob drink
    State.TASK_RETURN:    "plod",         # heavy heading-home walk
    State.SCRATCHING:     "scratch",      # _draw_sleeping + kicking back leg
    State.CHEWING:        "chew",         # _draw_standing + head-bob + bone
    State.SNIFF_WALK:     "sniff-walk",   # slow nose-down walk, pause-and-go
    State.ROLL_OVER:      "roll-over",    # onto the back, paws paddle, right itself
    State.BARKING:        "bark",         # head back, mouth open, two quick bobs
    State.BEG:            "beg-sit-up",   # torso up on haunches, front paws dangle
    State.GREETING:       "greet-wag",    # little hops + fast wag (+ optional bark)
    State.ZOOMIES:        "dash",         # flat-out sprint, direction flips
    State.CLIMBING:       "climb-up",     # paws over the ledge, haul up, settle
                                          # (no sprite clip yet — open art item;
                                          # procedural placeholder until then)
}


class Gait:
    """Locomotion parameters: how the legs/body move while a state travels."""
    __slots__ = ("name", "speed", "phase_rate", "swing", "bounce",
                 "head_down", "wag")

    def __init__(self, name, speed, phase_rate, swing, bounce, head_down, wag):
        self.name = name
        self.speed = speed              # px per tick
        self.phase_rate = phase_rate    # walk_phase increment per tick
        self.swing = swing              # leg swing amplitude (px)
        self.bounce = bounce            # whole-body vertical bounce (px)
        self.head_down = head_down      # head lowered by this many px
        self.wag = wag                  # tail wag amplitude while moving


GAITS = {
    "trot-brisk": Gait("trot-brisk", 1.5, 0.25, 5, 0.0, 0, 12),
    "plod":       Gait("plod",       0.9, 0.15, 3, 0.0, 3, 6),
    "scamper":    Gait("scamper",    2.6, 0.42, 7, 2.5, 0, 14),
    "sniff-walk": Gait("sniff-walk", 0.75, 0.12, 3, 0.0, 0, 4),
    "dash":       Gait("dash",       3.4, 0.50, 8, 3.0, 0, 14),
}

# Which gait each state travels with (None / missing = state doesn't travel).
STATE_GAIT = {
    State.WALKING:        "trot-brisk",
    State.TASK_RETURN:    "plod",
    State.RETURNING_BALL: "plod",
    State.FETCHING:       "scamper",
    State.SNIFF_WALK:     "sniff-walk",
    State.DRINKING:       "trot-brisk",   # approach phase only
    State.ZOOMIES:        "dash",
}


def get_taskbar_rect():
    """Return (left, top, right, bottom) of the taskbar in Qt logical pixels.

    Uses QScreen.availableGeometry() so coordinates are always in the same
    space as setGeometry() — no DPI-mismatch with SHAppBarMessage physical px.
    """
    screen = QApplication.primaryScreen()
    sg = screen.geometry()        # full screen, logical px
    ag = screen.availableGeometry()  # area excluding taskbar, logical px

    # QRect.bottom() == y + height - 1  (last included row)
    # QRect.right()  == x + width  - 1  (last included col)
    if ag.bottom() < sg.bottom():           # taskbar at bottom (typical)
        tb_top    = ag.bottom() + 1         # first row of taskbar
        tb_bottom = sg.bottom() + 1         # one past last screen row
        tb_left   = sg.left()
        tb_right  = sg.right() + 1
    else:                                   # fallback — assume 48 px at bottom
        tb_bottom = sg.bottom() + 1
        tb_top    = tb_bottom - 48
        tb_left   = sg.left()
        tb_right  = sg.right() + 1

    return tb_left, tb_top, tb_right, tb_bottom


# Tall enough for the dog at the largest size toggle (2x: ~140px of sprite
# above the feet) plus headroom for the rising zzz bubbles. Everything draws
# bottom-anchored, so extra height just extends the invisible masked area up.
WIN_H = 190
# Drawing uses DOG_BASE as the exclusive bottom of bounding rects, so the last
# painted pixel row is DOG_BASE - 1 = WIN_H - 1, which maps to tb_top.
DOG_BASE = WIN_H


class ZzzBubble:
    def __init__(self, x, y, size):
        self.x = float(x)
        self.y = float(y)
        self.size = size
        self.alpha = 220.0
        self.dx = random.uniform(-0.3, 0.3)

    def tick(self):
        self.y -= 0.5
        self.x += self.dx
        self.alpha -= 2.2
        return self.alpha > 0


class Biscuit(QWidget):
    def __init__(self):
        super().__init__()

        screen = QApplication.primaryScreen().geometry()
        self.sw = screen.width()
        self.sh = screen.height()

        self.tb_left, self.tb_top, self.tb_right, self.tb_bottom = get_taskbar_rect()

        # Full-width static window; dog and decorations drawn at their screen-x coords
        # (window-local x == screen x because window always starts at x=0).
        self.win_w = self.sw

        # Per-behavior on/off switches + art kit/scale, persisted to
        # %APPDATA%\Persi. Behaviors read their switch when they would fire;
        # the Test menu bypasses the switches by setting states directly.
        self.settings = Settings()

        # Size toggle: multiplies the dog and the corner props (sprite frames
        # scale nearest-neighbor via a painter transform, so pixels stay crisp).
        self.art_scale = min(2.0, max(0.5, float(self.settings.get("art.scale"))))

        # Corner home positions (screen x = window-local x), spaced by the
        # art scale so the props never overlap when drawn larger.
        self._layout_corner()

        # Dog starts on the bed
        self.dog_sx = float(self.bed_cx)

        self.state = State.SLEEPING
        self.paused = False
        self.facing = -1   # -1=left  1=right

        self._ticks = 0
        self.breath_phase = 0.0
        self.tail_phase = 0.0
        self.walk_phase = 0.0
        self.bounce_val = 0.0

        self.tongue = False
        self.state_frames = 0
        self.walk_dir = -1
        self.returning = False  # True while dog is walking back to the bed

        self.cursor_near = False
        self.cursor_settle = 0

        self.bubbles = []
        self.zzz_cd = 200

        self.walk_min = float(self.tb_left + 100)
        # walk_max (return-to-bed bound) is kept in sync by _layout_corner()

        self.startup_enabled = self._check_startup()

        # Ball state
        self.ball_x = float(self.ball_cx)
        self.ball_visible = True

        # Bowl state
        self.bowl_full = True

        # Task system
        self.task_phase = 0
        self.task_frames = 0
        self.stretch_factor = 0.0

        # Sniff-walk sub-state
        self.sniff_dest = 0.0
        self.sniff_next_pause = 0.0

        # Zoomies sub-state (task_phase counts dashes, state_frames = total)
        self.zoom_left = 0.0
        self.zoom_right = 0.0
        self.zoom_dest = 0.0

        # Greet: on launch, and on cursor returning after a long idle gap
        self._greet_bark = False
        self.greet_idle_s = 600.0        # cursor idle gap that counts as "away"
        self.greet_cooldown_s = 600.0    # at most one return-greet per this
        self._last_cursor_pos = None
        self._last_cursor_move_t = time.monotonic()
        self._last_greet_t = 0.0

        # Idle fidget layer: small motions that never change self.state.
        # The engine picks them; the _draw_* methods read self.fidgets.active
        # and apply small deltas on the base pose.
        self.fidgets = FidgetEngine()

        # Roll-over command gesture: armed by a click on the dog, completed by
        # circling the cursor around the dog ~3 times (pure cursor math).
        self.gesture = CircleGestureRecognizer()

        # Phase 6 sprite kits (assets/manifest.json + drop-in assets/kits/*).
        # self.sprites is the active kit's SpriteSet, or None for the
        # procedural renderer. Per-state fallback also happens inside
        # _sprite_draw, so partial asset sets are fine while art is iterated.
        self.sprite_kits = available_kits() if SpriteSet is not None else {}
        self._kit_cache = {}
        self.art_kit = self.settings.get("art.kit")
        if self.art_kit != "procedural" and self.art_kit not in self.sprite_kits:
            # Stored kit folder is gone/renamed/hand-edited — fall back and
            # heal the file, so the menu's checkmark matches what's persisted.
            self.art_kit = "pixel" if "pixel" in self.sprite_kits else "procedural"
            self.settings.set("art.kit", self.art_kit)
        self.sprites = self._load_kit(self.art_kit)

        # Reminder pending flags
        self.stretch_pending = False
        self.water_pending = False

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._place_window()

        t = QTimer(self)
        t.timeout.connect(self._on_tick)
        t.start(33)

        # Single-shot timer: fires once after a random sleep duration, starts a walk.
        # Re-armed each time the dog returns to the bed.
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setSingleShot(True)
        self._sleep_timer.timeout.connect(self._start_walk)
        self._arm_sleep_timer()

        self._stretch_timer = QTimer(self)
        self._stretch_timer.timeout.connect(self._on_stretch_timer)
        self._stretch_timer.start(30 * 60 * 1000)   # every 30 minutes

        self._water_timer = QTimer(self)
        self._water_timer.timeout.connect(self._on_water_timer)
        self._water_timer.start(60 * 60 * 1000)     # every 60 minutes

        self.show()
        self._assert_topmost()

        # Launch sequence: climb up from behind the taskbar ledge, then greet.
        # With the climb switched off, greet shortly after launch as before
        # (reactive.greet switch checked at fire time either way).
        self._greet_timer = QTimer(self)
        self._greet_timer.setSingleShot(True)
        self._greet_timer.timeout.connect(self._launch_greet)
        self._climb_then_greet = False
        if self.settings.get("reactive.startup_climb"):
            # Order matters: _start_climb() clears _climb_then_greet (so a
            # later Test-menu climb never chains a greet), then we arm it for
            # this one launch climb.
            self._start_climb()
            self._climb_then_greet = True
        else:
            self._greet_timer.start(1800)

        # === DEBUG HUD (dev tool — delete this block + debug_hud.py to remove) ===
        from debug_hud import DebugHUD
        self.hud_enabled = self.settings.get("debug.hud")
        self._hud = DebugHUD(self)
        if self.hud_enabled:
            self._hud.show()
        # === end DEBUG HUD ===

    def current_anim(self):
        """The animation label for the current state (see ANIMATION map)."""
        return ANIMATION.get(self.state, "?")

    def _active_gait(self):
        """The Gait the dog is travelling with right now, else None.

        Phase-aware: states that pause mid-behavior (drink, pickup, sniff
        pause) only report a gait while their travelling sub-phase is active.
        """
        if self.state in (State.DRINKING, State.FETCHING, State.SNIFF_WALK) \
                and self.task_phase != 0:
            return None
        name = STATE_GAIT.get(self.state)
        return GAITS[name] if name is not None else None

    # ── art kit / size ───────────────────────────────────────────────────────

    def _layout_corner(self):
        """Corner home positions, spaced by the art scale so the bed, bowl and
        ball keep clear of each other at every size. Dog walk targets reference
        these, so they stay consistent automatically."""
        k = self.art_scale
        self.bed_cx = self.tb_right - int(160 * k)
        self.bowl_cx = self.tb_right - int(95 * k)
        self.ball_cx = self.tb_right - int(65 * k)
        self.walk_max = float(self.bed_cx)

    def _load_kit(self, name):
        """SpriteSet for a kit name, or None (= procedural). Cached per kit so
        switching back and forth in the menu doesn't reload frames."""
        if SpriteSet is None or name == "procedural" or name not in self.sprite_kits:
            return None
        if name not in self._kit_cache:
            try:
                self._kit_cache[name] = SpriteSet(self.sprite_kits[name])
            except Exception:
                self._kit_cache[name] = None
        return self._kit_cache[name]

    def _set_art_kit(self, name):
        self.art_kit = name
        self.settings.set("art.kit", name)
        self.sprites = self._load_kit(name)

    def _set_art_scale(self, k):
        on_bed = abs(self.dog_sx - self.bed_cx) < 3
        ball_home = abs(self.ball_x - self.ball_cx) < 5
        self.art_scale = k
        self.settings.set("art.scale", k)
        self._layout_corner()
        # Re-pin whatever was sitting at a home position to the new layout
        if on_bed:
            self.dog_sx = float(self.bed_cx)
        if ball_home:
            self.ball_x = float(self.ball_cx)
        # Zoomies caches its dash endpoints relative to bed_cx, which just
        # moved — recompute them (keeping the current heading) so the dog
        # doesn't dash through the relocated bed/corner.
        if self.state == State.ZOOMIES:
            heading_right = self.zoom_dest > self.dog_sx
            self._set_zoom_bounds()
            self.zoom_dest = self.zoom_right if heading_right else self.zoom_left

    def _one_shot_ticks(self, name, default):
        """Duration for a one-shot behavior: the active kit's clip length, so
        the state machine and the animation end together; the procedural
        default otherwise."""
        s = self.sprites
        if s is not None and s.has(name):
            return s.clips[name].total
        return default

    # ── window placement ─────────────────────────────────────────────────────

    def _place_window(self):
        # wy + WIN_H - 1 == tb_top  →  last window pixel row lands on tb_top.
        wy = self.tb_top - WIN_H + 1
        self.setGeometry(0, wy, self.win_w, WIN_H)
        self._update_mask()

    def _update_mask(self):
        dx = int(self.dog_sx)
        k = self.art_scale
        if self.sprites is not None:
            # Sprite frames are 128 wide with content up to ~70px above the
            # feet (measure_bounds.py) — one rect for every pose, otherwise
            # the mask clips the nose/tail off the wider clips. The +14 over
            # 70 is headroom for the bounce of EXCITED/GREETING (up to 8px),
            # which lifts the whole frame and would otherwise clip the head.
            dog_r = QRect(dx - int(64 * k), WIN_H - int(84 * k),
                          int(128 * k), int(84 * k))
        elif self.state in (State.SLEEPING, State.STRETCHING, State.SCRATCHING,
                            State.ROLL_OVER):
            dog_r = QRect(dx - int(60 * k), WIN_H - int(38 * k),
                          int(120 * k), int(38 * k))
        else:
            dog_r = QRect(dx - int(52 * k), WIN_H - int(75 * k),
                          int(104 * k), int(75 * k))

        decor_left  = self.bed_cx - int(42 * k)
        decor_right = self.ball_cx + int(12 * k)
        decor_r = QRect(decor_left, WIN_H - int(25 * k),
                        decor_right - decor_left, int(25 * k))

        region = QRegion(dog_r) | QRegion(decor_r)

        # Ball away from its home corner also needs to be in mask to be visible
        if self.ball_visible and abs(self.ball_x - self.ball_cx) > 20:
            bx = int(self.ball_x)
            region |= QRegion(QRect(bx - int(12 * k), WIN_H - int(20 * k),
                                    int(24 * k), int(20 * k)))

        self.setMask(region)

    def _assert_topmost(self):
        hwnd = int(self.winId())
        ctypes.WinDLL("user32").SetWindowPos(
            hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    # ── tick ─────────────────────────────────────────────────────────────────

    def _on_tick(self):
        self._ticks += 1
        self.breath_phase += 0.05
        self.tail_phase += 0.15
        g = self._active_gait()
        self.walk_phase += g.phase_rate if g is not None else 0.25

        cp = QCursor.pos()

        # Greet on return: cursor moves again after a long still gap.
        # (Polls the same cursor position as everything else — no hooks.)
        if self._last_cursor_pos is None or cp != self._last_cursor_pos:
            now = time.monotonic()
            gap = now - self._last_cursor_move_t
            self._last_cursor_move_t = now
            self._last_cursor_pos = cp
            if (gap > self.greet_idle_s
                    and now - self._last_greet_t > self.greet_cooldown_s):
                self._maybe_greet()

        # Roll-over circle gesture (armed by a dog click; pure cursor math)
        dog_center_y = self.tb_top - int(30 * self.art_scale)
        if self.gesture.tick(self.dog_sx, dog_center_y, cp.x(), cp.y()):
            if (not self.paused
                    and self.settings.get("command.roll_over")
                    and self.state in (State.SLEEPING, State.ALERT,
                                       State.EXCITED)):
                self._start_roll_over()

        # Cursor proximity (behavior switch: interactive.cursor_alert)
        if self.settings.get("interactive.cursor_alert"):
            dog_screen_cy = self.tb_top - int(25 * self.art_scale)
            dist = math.hypot(cp.x() - self.dog_sx, cp.y() - dog_screen_cy)
            was_near = self.cursor_near
            self.cursor_near = dist < 150

            if self.cursor_near:
                self.facing = -1 if cp.x() < self.dog_sx else 1
                if not was_near and self.state == State.SLEEPING:
                    self.state = State.ALERT
                    self.bubbles.clear()
                self.cursor_settle = 90

            if not self.cursor_near and self.cursor_settle > 0:
                self.cursor_settle -= 1
                if self.cursor_settle == 0 and self.state == State.ALERT:
                    self.state = State.SLEEPING
        elif self.cursor_near or self.cursor_settle > 0:
            # Switch turned off mid-alert: settle straight back to sleep
            self.cursor_near = False
            self.cursor_settle = 0
            if self.state == State.ALERT:
                self.state = State.SLEEPING

        if not self.paused:
            self._update_state()

        # Idle fidgets — only while resting (lying) or alert (standing); the
        # engine cancels any in-flight fidget the moment the pose stops being
        # eligible, so fidgets can never overlap a real behavior or one-shot.
        if self.paused:
            self.fidgets.tick(None)
        else:
            if (self.state == State.SLEEPING
                    and self.settings.get("idle.fidgets_lying")):
                self.fidgets.tick(POSE_LYING)
            elif (self.state == State.ALERT
                    and self.settings.get("idle.fidgets_standing")):
                self.fidgets.tick(POSE_STANDING)
            else:
                self.fidgets.tick(None)
            fa = self.fidgets.active
            # The sigh's exhale releases one soft "z" puff at the swell's peak.
            if (fa is not None and fa.name == "sigh"
                    and fa.ticks == fa.total // 3):
                k = self.art_scale
                hx = int(self.dog_sx) + self.facing * int(25 * k)
                self.bubbles.append(ZzzBubble(hx, DOG_BASE - int(42 * k),
                                              max(6, int(9 * k))))

        # Zzz
        if self.state == State.SLEEPING and not self.paused:
            self.zzz_cd -= 1
            if self.zzz_cd <= 0:
                self.zzz_cd = random.randint(130, 230)
                k = self.art_scale
                hx = int(self.dog_sx) + self.facing * int(25 * k)
                hy = DOG_BASE - int(38 * k)
                self.bubbles.append(ZzzBubble(
                    hx, hy, max(6, int(random.randint(7, 11) * k))))

        self.bubbles = [b for b in self.bubbles if b.tick()]

        self._update_mask()
        self.update()

        if self._ticks % 180 == 0:
            self._assert_topmost()

        # === DEBUG HUD (dev tool — delete this block to remove) ===
        if getattr(self, "hud_enabled", False) and self._hud is not None:
            self._hud.refresh(self)
        # === end DEBUG HUD ===

    def _update_state(self):
        self._check_pending()

        if self.state == State.WALKING:
            if self.returning:
                # Walking home — always move toward bed_cx
                self.dog_sx += GAITS["trot-brisk"].speed * self.walk_dir
                if self.dog_sx >= self.bed_cx:
                    self.dog_sx = float(self.bed_cx)
                    self.returning = False
                    self.state = State.SLEEPING
                    self.facing = -1  # settle facing left on the bed
                    self._arm_sleep_timer()
            else:
                # Roaming — bounce between walk_min and walk_max
                self.dog_sx += GAITS["trot-brisk"].speed * self.walk_dir
                if self.dog_sx >= self.walk_max:
                    self.walk_dir = -1
                    self.facing = -1
                elif self.dog_sx <= self.walk_min:
                    self.walk_dir = 1
                    self.facing = 1

                self.state_frames -= 1
                if self.state_frames <= 0:
                    # Time's up — head home; dog is always left-of or at bed_cx
                    self.returning = True
                    self.walk_dir = 1
                    self.facing = 1

        elif self.state == State.EXCITED:
            self.bounce_val = abs(math.sin(self._ticks * 0.25)) * 8
            self.state_frames -= 1
            if self.state_frames <= 0:
                self.state = State.SLEEPING
                self.tongue = False
                self.bounce_val = 0.0
                self._arm_sleep_timer()

        elif self.state == State.FETCHING:
            self._update_fetching()
        elif self.state == State.RETURNING_BALL:
            self._update_returning_ball()
        elif self.state == State.STRETCHING:
            self._update_stretching()
        elif self.state == State.DRINKING:
            self._update_drinking()
        elif self.state == State.TASK_RETURN:
            self._update_task_return()
        elif self.state == State.SCRATCHING:
            self._update_scratching()
        elif self.state == State.CHEWING:
            self._update_chewing()
        elif self.state == State.SNIFF_WALK:
            self._update_sniff_walk()
        elif self.state == State.ROLL_OVER:
            self._update_roll_over()
        elif self.state == State.BARKING:
            self._update_barking()
        elif self.state == State.BEG:
            self._update_beg()
        elif self.state == State.GREETING:
            self._update_greeting()
        elif self.state == State.ZOOMIES:
            self._update_zoomies()
        elif self.state == State.CLIMBING:
            self._update_climbing()

    def _arm_sleep_timer(self):
        """Schedule the next walk after 4–8 minutes of sleep."""
        ms = random.randint(4 * 60 * 1000, 8 * 60 * 1000)
        self._sleep_timer.start(ms)

    def _start_walk(self):
        """Called when the sleep timer fires. Start a roaming walk."""
        if self.paused or self.cursor_near or self.state != State.SLEEPING:
            # Not ready — retry in 30 s without resetting the full sleep cycle
            self._sleep_timer.start(30_000)
            return

        # If ball was thrown and never fetched, go get it first
        if self.ball_visible and abs(self.ball_x - self.ball_cx) > 20:
            self.state = State.FETCHING
            self.task_phase = 0
            self.task_frames = 0
            self.returning = False
            self.bubbles.clear()
            return

        # Weighted pick among the ambient behaviors that are switched on
        # (zoomies is deliberately rare)
        pool = [(b, w) for b, key, w in (('walk', 'idle.wander_walk', 3),
                                         ('scratch', 'idle.scratch', 3),
                                         ('chew', 'idle.chew', 3),
                                         ('sniff', 'idle.sniff_walk', 3),
                                         ('zoomies', 'idle.zoomies', 1))
                if self.settings.get(key)]
        if not pool:
            self._arm_sleep_timer()     # everything off: keep sleeping
            return
        behavior = random.choices([b for b, _ in pool],
                                  weights=[w for _, w in pool])[0]
        self.bubbles.clear()
        self.task_phase = 0
        self.task_frames = 0

        if behavior == 'zoomies':
            self._start_zoomies()
        elif behavior == 'scratch':
            self.state = State.SCRATCHING
            self.state_frames = random.randint(90, 120)   # 3–4 s
        elif behavior == 'chew':
            self.state = State.CHEWING
            self.state_frames = random.randint(240, 300)  # 8–10 s
        elif behavior == 'sniff':
            self.state = State.SNIFF_WALK
            sniff_dist = random.randint(100, 400)
            self.sniff_dest = max(self.walk_min, self.dog_sx - sniff_dist)
            self.sniff_next_pause = self.dog_sx - random.randint(20, 30)
            self.facing = -1
        else:  # normal walk
            self.state = State.WALKING
            self.returning = False
            self.walk_dir = -1
            self.facing = -1
            self.state_frames = random.randint(30 * 30, 90 * 30)

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setRenderHint(QPainter.Antialiasing)
        self._draw(p)
        p.end()

    def _draw(self, p):
        cx = int(self.dog_sx)
        base = DOG_BASE - int(self.bounce_val)
        f = self.facing

        BROWN = QColor(185, 118, 55)
        DARK  = QColor(118, 70, 22)
        BLACK = QColor(32, 22, 12)
        WHITE = QColor(255, 255, 255)
        PINK  = QColor(230, 88, 88)
        ZZZ   = QColor(130, 148, 228)

        # GREETING borrows the excited flair: fast wag, tongue, bounce
        excited  = self.state in (State.EXCITED, State.GREETING)
        alert    = self.state == State.ALERT

        # Corner home objects drawn first
        self._draw_corner(p)

        fa = self.fidgets.active   # idle fidget delta (None outside SLEEPING/ALERT)

        # Size toggle: everything dog-shaped (sprite or procedural) scales
        # around the point where the feet meet the taskbar. Pixmaps scale
        # nearest-neighbor (no SmoothPixmapTransform hint), so pixel art
        # stays crisp at any size.
        k = self.art_scale
        if k != 1.0:
            p.save()
            p.translate(cx, DOG_BASE)
            p.scale(k, k)
            p.translate(-cx, -DOG_BASE)

        # Phase 6 sprite renderer: if a clip covers the current state/fidget,
        # draw it and skip the procedural dog. Bubbles still drawn (procedural
        # zzz per the inventory). Falls through per-state when a clip is missing.
        if not self._sprite_draw(p, cx, base, f, fa):
            self._draw_dog_procedural(p, cx, base, f, fa, excited, alert,
                                      BROWN, DARK, BLACK, WHITE, PINK)

        if k != 1.0:
            p.restore()

        self._draw_bubbles(p, ZZZ)

    def _draw_dog_procedural(self, p, cx, base, f, fa, excited, alert,
                             BROWN, DARK, BLACK, WHITE, PINK):
        if self.state == State.CLIMBING:
            self._draw_climb(p, cx, base, f, BROWN, DARK, BLACK, WHITE, PINK)

        elif self.state == State.ROLL_OVER:
            self._draw_rollover(p, cx, base, f, BROWN, DARK, BLACK)

        elif self.state == State.BEG:
            self._draw_beg(p, cx, base, f, BROWN, DARK, BLACK, WHITE, PINK)

        elif self.state == State.BARKING:
            bob = max(0.0, math.sin(self.task_frames * 0.5))
            head_up = int(bob * 6)
            bcx = cx - f * (head_up // 3)        # tiny recoil on each bob
            self._draw_standing(p, bcx, base, f, BROWN, DARK, BLACK, WHITE,
                                PINK, False, False, False, head_bob=-head_up)
            if bob > 0.35:
                self._draw_bark_mouth(p, bcx, base, f, -head_up)

        elif self.state in (State.SLEEPING, State.STRETCHING):
            if fa is not None and fa.name == "scratch":
                # Lying scratch fidget: same body jitter + kicking leg as the
                # full SCRATCHING state, just short and without a state change.
                jx = int(math.sin(fa.ticks * 0.65) * 1.5)
                jy = int(math.cos(fa.ticks * 0.73) * 1.0)
                self._draw_sleeping(p, cx + jx, base + jy, f, BROWN, DARK, BLACK)
                self._draw_scratch_leg(p, cx + jx, base + jy, f, DARK,
                                       frames=fa.ticks)
            else:
                self._draw_sleeping(p, cx, base, f, BROWN, DARK, BLACK)

        elif self.state == State.SCRATCHING:
            shake_x = int(math.sin(self.task_frames * 0.65) * 1.5)
            shake_y = int(math.cos(self.task_frames * 0.73) * 1.0)
            self._draw_sleeping(p, cx + shake_x, base + shake_y, f, BROWN, DARK, BLACK)
            self._draw_scratch_leg(p, cx + shake_x, base + shake_y, f, DARK)

        elif self.state == State.CHEWING:
            head_bob = int(max(0, math.sin(self.task_frames * 0.30)) * 5)
            self._draw_standing(p, cx, base, f, BROWN, DARK, BLACK, WHITE, PINK,
                                False, False, False, head_bob=head_bob)
            self._draw_bone(p, cx, base, f, head_bob)

        elif self.state == State.SNIFF_WALK:
            is_sniff_walking = (self.task_phase == 0)
            head_bob = 8 if is_sniff_walking else 10  # nose down while walking/pausing
            self._draw_standing(p, cx, base, f, BROWN, DARK, BLACK, WHITE, PINK,
                                is_sniff_walking, False, False, head_bob=head_bob)

        else:
            is_walking_anim = self.state in (
                State.WALKING, State.FETCHING, State.RETURNING_BALL, State.TASK_RETURN
            ) or (self.state == State.DRINKING and self.task_phase == 0)
            head_bob = 0
            if self.state == State.DRINKING and self.task_phase == 1 and self.bowl_full:
                head_bob = int(max(0, math.sin(self.task_frames * 0.25)) * 10)
            g = self._active_gait()
            if is_walking_anim and g is not None:
                head_bob += g.head_down      # plod travels head-low

            # Standing (ALERT) fidgets handled at this level: whole-body
            # shake-off jitter, and the bone-from-pocket chew's bob + bone.
            if alert and fa is not None and fa.name == "shake-off":
                amp = math.sin(fa.progress * math.pi)        # ramp in and out
                cx += int(math.sin(fa.ticks * 1.15) * 3 * amp)
            if alert and fa is not None and fa.name == "bone-chew":
                if 0.2 < fa.progress < 0.85:                 # gnawing window
                    head_bob = int(max(0, math.sin(fa.ticks * 0.30)) * 5)

            self._draw_standing(p, cx, base, f, BROWN, DARK, BLACK, WHITE, PINK,
                                is_walking_anim, excited, alert, head_bob=head_bob)

            if (alert and fa is not None and fa.name == "bone-chew"
                    and 0.15 < fa.progress < 0.9):
                self._draw_bone(p, cx, base, f, head_bob)

        # Ball carried by dog (RETURNING_BALL state; mouth rides at plod height)
        if self.state == State.RETURNING_BALL:
            r = 6
            bx = int(self.dog_sx) + self.facing * 28
            by = base - 45 + GAITS["plod"].head_down
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(215, 70, 45))
            p.drawEllipse(bx - r, by, r * 2, r * 2)

    def _draw_bubbles(self, p, ZZZ):
        for b in self.bubbles:
            alpha = max(0, min(255, int(b.alpha)))
            p.save()
            p.setOpacity(alpha / 255.0)
            p.setFont(QFont("Arial", b.size, QFont.Bold))
            p.setPen(QPen(ZZZ))
            p.drawText(int(b.x), int(b.y), "z")
            p.restore()

    def _sprite_draw(self, p, cx, base, f, fa):
        """Phase 6: draw the dog from sprite clips. Returns True if drawn.

        Clip choice mirrors the procedural dispatch: an active idle fidget
        replaces the base clip while it plays; travelling states use their
        gait clip; everything else uses ANIMATION[state]. Loops index on the
        global tick counter, one-shots on task_frames (ticks since the
        behavior started).
        """
        s = self.sprites
        if s is None:
            return False

        if fa is not None and self.state in (State.SLEEPING, State.ALERT):
            pm = s.fidget_pixmap(fa.name, fa.progress, f)
            if pm is not None:
                s.draw_dog(p, pm, cx, base)
                return True

        # Sniff-walk plays as two sub-loops of one clip: the stride frames
        # while travelling, the 2 nose-down sniff frames during a pause
        # (task_phase 1) — instead of looping the whole clip through a pause.
        if self.state == State.SNIFF_WALK and s.has("sniff-walk"):
            n = len(s.clips["sniff-walk"].frames)
            if self.task_phase == 0:
                pm = s.get_range("sniff-walk", self._ticks, f, 0, n - 3)
            else:
                pm = s.get_range("sniff-walk", self._ticks, f, n - 2, n - 1)
            if pm is not None:
                s.draw_dog(p, pm, cx, base)
                return True

        g = self._active_gait()
        name = g.name if g is not None else ANIMATION.get(self.state)
        if name is None or not s.has(name):
            return False
        tick = self._ticks if s.clips[name].loop else self.task_frames
        pm = s.get(name, tick, f)
        if pm is None:
            return False
        s.draw_dog(p, pm, cx, base)
        return True

    def _push_anchor_scale(self, p, ax, ay):
        """Painter transform scaling by the size toggle around an anchor
        point (a thing's own ground contact, so it doesn't drift sideways).
        Returns True if a transform was pushed — caller must p.restore()."""
        k = self.art_scale
        if k == 1.0:
            return False
        p.save()
        p.translate(ax, ay)
        p.scale(k, k)
        p.translate(-ax, -ay)
        return True

    def _blit_prop(self, p, pm, cx, ground):
        pushed = self._push_anchor_scale(p, cx, ground)
        p.drawPixmap(cx - pm.width() // 2, ground - pm.height(), pm)
        if pushed:
            p.restore()

    def _draw_corner(self, p):
        # Phase 6 sprite props (bed, bowl, ball); procedural fallback below.
        if self.sprites is not None:
            ground = WIN_H
            bed = self.sprites.prop("bed")
            bowl = self.sprites.prop("bowl-full" if self.bowl_full
                                     else "bowl-empty")
            if bed is not None and bowl is not None:
                self._blit_prop(p, bed, self.bed_cx, ground)
                self._blit_prop(p, bowl, self.bowl_cx, ground)
                ball = self.sprites.prop("ball")
                if self.ball_visible and ball is not None:
                    self._blit_prop(p, ball, int(self.ball_x), ground)
                return
        self._draw_corner_procedural(p)

    def _draw_corner_procedural(self, p):
        BED_FILL   = QColor(250, 250, 250)   # white so dog is visible on it
        BED_RIM    = QColor(185, 185, 185)
        BOWL_FULL  = QColor(148, 198, 222)
        BOWL_EMPTY = QColor(175, 168, 158)
        BOWL_RIM   = QColor(192, 192, 192)
        BALL_COL   = QColor(215, 70, 45)
        SHINE      = QColor(255, 200, 185, 155)

        ground = WIN_H

        # Bed
        pushed = self._push_anchor_scale(p, self.bed_cx, ground)
        bw, bh = 72, 18
        p.setPen(QPen(BED_RIM, 1.5))
        p.setBrush(BED_FILL)
        p.drawEllipse(self.bed_cx - bw // 2, ground - bh, bw, bh)
        p.setPen(QPen(BED_RIM, 1, Qt.DotLine))
        p.setBrush(Qt.NoBrush)
        p.drawLine(self.bed_cx - bw // 2 + 7, ground - bh // 2,
                   self.bed_cx + bw // 2 - 7, ground - bh // 2)
        if pushed:
            p.restore()

        # Water bowl — full=blue, empty=grey
        pushed = self._push_anchor_scale(p, self.bowl_cx, ground)
        bw2, bh2 = 22, 12
        p.setPen(QPen(BOWL_RIM, 1.5))
        p.setBrush(BOWL_FULL if self.bowl_full else BOWL_EMPTY)
        p.drawEllipse(self.bowl_cx - bw2 // 2, ground - bh2, bw2, bh2)
        if pushed:
            p.restore()

        # Ball — drawn at ball_x (may be corner or somewhere on taskbar)
        if self.ball_visible:
            bx = int(self.ball_x)
            pushed = self._push_anchor_scale(p, bx, ground)
            r = 8
            p.setPen(Qt.NoPen)
            p.setBrush(BALL_COL)
            p.drawEllipse(bx - r, ground - r * 2, r * 2, r * 2)
            p.setBrush(SHINE)
            p.drawEllipse(bx - r + 2, ground - r * 2 + 2, r // 2 + 2, r // 2 + 1)
            if pushed:
                p.restore()

    def _draw_sleeping(self, p, cx, base, f, BROWN, DARK, BLACK):
        # Active lying fidget (engine guarantees None outside SLEEPING; the
        # 'scratch' fidget is handled by the caller, so no delta here).
        fa = self.fidgets.active
        fname = fa.name if fa is not None else None
        fticks = fa.ticks if fa is not None else 0
        fswell = math.sin(fa.progress * math.pi) if fa is not None else 0.0

        if fname == "resettle":
            # Body shifts toward the tail a touch and re-curls (compresses).
            cx += int(fswell * -f * 4)

        stretch_extra = int(self.stretch_factor * 25)
        bw = 68 + stretch_extra
        bh = int(18 + math.sin(self.breath_phase) * 1.5)
        if fname == "sigh":
            bh += int(fswell * 3)          # one larger breath swell
        elif fname == "resettle":
            bh -= int(fswell * 2)
        body_top = base - bh

        # Tail (at the back = opposite of facing)
        tail_lift = fswell * 7 if fname == "tail-twitch" else 0.0
        tx = cx - f * (bw // 2 - 4)
        p.setPen(QPen(DARK, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        tp = QPainterPath()
        tp.moveTo(tx, body_top + bh // 2)
        tp.quadTo(tx - f * (-10), body_top - 6 - tail_lift * 0.5,
                  tx - f * (-4),  body_top - 17 - tail_lift)
        p.drawPath(tp)

        # Body
        p.setPen(Qt.NoPen)
        p.setBrush(BROWN)
        p.drawEllipse(cx - bw // 2, body_top, bw, bh)

        # Head (at front = facing side)
        hr = 13
        hcx = cx + f * (bw // 2 - 5)
        hcy = body_top + bh // 2 - 4
        p.setBrush(BROWN)
        p.drawEllipse(int(hcx - hr), int(hcy - hr), hr * 2, hr * 2)

        # Ear (flick = quick lift-and-settle)
        ear_dy = -int(fswell * 4) if fname == "ear-flick" else 0
        ear_h = 14 - (int(fswell * 3) if fname == "ear-flick" else 0)
        p.setBrush(DARK)
        p.drawEllipse(int(hcx - f * 3 - 5), int(hcy - hr + 3 + ear_dy), 9, ear_h)

        # Eye: closed arc, or a sliver cracking open mid-fidget
        if fname == "eye-crack" and 0.25 < fa.progress < 0.75:
            p.setPen(Qt.NoPen)
            p.setBrush(BLACK)
            p.drawEllipse(int(hcx + f * 3 - 3), int(hcy - 3), 6, 3)
        else:
            p.setPen(QPen(BLACK, 1.5, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(int(hcx + f * 3 - 4), int(hcy - 4), 8, 6, 0, -180 * 16)

        # Nose / yawn (yawn opens during stretch)
        nose_dx = int(round(math.sin(fticks * 0.9) * 1.5)) \
            if fname == "nose-twitch" else 0
        p.setPen(Qt.NoPen)
        if self.stretch_factor > 0.4:
            yawn_h = max(2, int(self.stretch_factor * 8))
            p.setBrush(QColor(55, 28, 18))
            p.drawEllipse(int(hcx + f * 9 - 3), int(hcy + 2), 7, yawn_h)
        else:
            p.setBrush(BLACK)
            p.drawEllipse(int(hcx + f * 9 - 3 + nose_dx), int(hcy + 2), 7, 5)

        # Legs tucked (dream-kick = alternating little twitches)
        kick = math.sin(fticks * 1.1) * 2 if fname == "dream-kick" else 0.0
        p.setBrush(DARK)
        for i, lo in enumerate([-20, -7, 7, 20]):
            leg_dx = int(kick) if i % 2 == 0 else -int(kick)
            p.drawRoundedRect(cx + lo - 3 + leg_dx, base - 9, 6, 9, 3, 3)

    def _draw_standing(self, p, cx, base, f, BROWN, DARK, BLACK, WHITE, PINK,
                       walking, excited, alert, head_bob=0):
        # Standing fidget deltas only apply in ALERT (the standing idle pose);
        # shake-off and bone-chew are handled by the caller in _draw.
        fa = self.fidgets.active if alert else None
        fname = fa.name if fa is not None else None
        fswell = math.sin(fa.progress * math.pi) if fa is not None else 0.0

        sit = 0.0                       # 0 = standing, 1 = fully sat
        if fname == "sit":
            pr = fa.progress            # ramp down, hold, stand back up
            if pr < 0.25:
                sit = pr / 0.25
            elif pr > 0.8:
                sit = (1.0 - pr) / 0.2
            else:
                sit = 1.0

        # Gait while travelling: leg swing / body bounce / wag come from it
        gait = self._active_gait() if walking else None
        if gait is not None and gait.bounce > 0:
            base -= int(abs(math.sin(self.walk_phase)) * gait.bounce)

        bw = 52
        bh = 17
        leg_len = 17
        body_bottom = base - leg_len
        body_top = body_bottom - bh

        # Weight-shift fidget: body/head/tail lean back a touch; legs stay put
        lean = int(fswell * -f * 3) if fname == "weight-shift" else 0

        # Legs
        p.setPen(Qt.NoPen)
        p.setBrush(DARK)
        leg_xs = [-18, -6, 8, 20]
        if walking:
            sw = math.sin(self.walk_phase) * (gait.swing if gait else 5)
            swings = [-sw, sw, sw, -sw]
        else:
            swings = [0.0] * 4
        for i, lx in enumerate(leg_xs):
            extra = abs(swings[i])
            ll = leg_len + extra
            is_rear = (lx < 0) if f > 0 else (lx > 0)
            if sit > 0 and is_rear:     # rear pair folds under the hips
                ll -= sit * 10
            p.drawRoundedRect(int(cx + lx - 2), body_bottom - 1,
                              5, int(ll), 2, 2)

        # Body (sitting tips it down at the rear, pivoting at the front hip)
        p.setBrush(BROWN)
        if sit > 0:
            pivot_x = cx + f * (bw // 2 - 8)
            p.save()
            p.translate(pivot_x, body_bottom)
            p.rotate(-f * sit * 14)
            p.translate(-pivot_x, -body_bottom)
            p.drawEllipse(cx + lean - bw // 2, body_top, bw, bh)
            p.restore()
        else:
            p.drawEllipse(cx + lean - bw // 2, body_top, bw, bh)

        # Tail. ALERT's idle signature is a gentle sway — the full-speed wag
        # is reserved for walking/excited (and the wag-burst fidget).
        if walking and gait is not None:
            wag = math.sin(self.tail_phase) * gait.wag
        elif excited or walking:
            wag = math.sin(self.tail_phase) * 12
        elif alert:
            wag = math.sin(self.tail_phase * 0.45) * 5
            if fname == "wag-burst":
                wag = math.sin(self.tail_phase * 2.2) * 13 * max(0.35, fswell)
        else:
            wag = 5
        tx = cx + lean - f * (bw // 2 - 3)
        ty = body_top + bh // 2 + int(sit * 8)
        p.setPen(QPen(DARK, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        tp = QPainterPath()
        tp.moveTo(tx, ty)
        tp.quadTo(tx - f * 8, ty - 12, tx - f * 5, ty - 20 - wag)
        p.drawPath(tp)

        # Head
        hr = 13
        hcx = cx + lean + f * (bw // 2 - 2)
        hcy = body_top - 4 + head_bob - int(sit * 3)
        if fname == "head-tilt":
            hcx += int(f * fswell * 2)
            hcy += int(fswell * 3)
        elif fname == "look-around":
            # glance back over the shoulder, then forward again
            hcx += int(f * math.sin(fa.progress * 2 * math.pi) * -4)
        p.setPen(Qt.NoPen)
        p.setBrush(BROWN)
        p.drawEllipse(int(hcx - hr), int(hcy - hr), hr * 2, hr * 2)

        # Ear: pricked up in ALERT (its idle signature), relaxed otherwise
        ear_dx = int(f * fswell * 3) if fname == "ear-swivel" else 0
        p.setBrush(DARK)
        if alert:
            p.drawEllipse(int(hcx - f * 2 - 4 + ear_dx), int(hcy - hr - 6), 8, 16)
        else:
            p.drawEllipse(int(hcx - f * 2 - 5 + ear_dx), int(hcy - hr - 2), 9, 14)

        # Eye (blink fidget closes it for a beat)
        if fname == "blink":
            p.setPen(QPen(BLACK, 1.5, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(int(hcx + f * 4 - 4), int(hcy - 6), 8, 6, 0, -180 * 16)
            p.setPen(Qt.NoPen)
        else:
            p.setBrush(BLACK)
            p.drawEllipse(int(hcx + f * 4 - 3), int(hcy - 7), 6, 6)
            p.setBrush(WHITE)
            p.drawEllipse(int(hcx + f * 4 - 1), int(hcy - 6), 2, 2)

        # Nose
        p.setPen(Qt.NoPen)
        p.setBrush(BLACK)
        p.drawEllipse(int(hcx + f * 9 - 3), int(hcy + 1), 7, 5)

        # Tongue
        if self.tongue or excited:
            p.setBrush(PINK)
            p.drawEllipse(int(hcx + f * 8 - 3), int(hcy + 7), 7, 8)

    # ── events ────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        lx = event.pos().x()
        ly = event.pos().y()

        k = self.art_scale
        if event.button() == Qt.LeftButton:
            # Mid-climb the dog has no footing yet — swallow every left click
            # until it tops out. (Must precede the ball check: a ball click
            # would otherwise start a fetch and strand the launch-greet chain.)
            if self.state == State.CLIMBING:
                return

            # Ball click — only when ball is at home corner and no fetch in progress
            if (self.settings.get("interactive.fetch_ball")
                    and self.ball_visible
                    and abs(self.ball_x - self.ball_cx) < 5
                    and abs(lx - self.ball_cx) < int(12 * k)
                    and ly > WIN_H - int(20 * k)
                    and self.state not in (State.FETCHING, State.RETURNING_BALL)):
                self._throw_ball()
                return

            # Bowl click — refill
            if abs(lx - self.bowl_cx) < int(13 * k) and ly > WIN_H - int(14 * k):
                self._refill_bowl()
                return

            # Any dog click arms the roll-over circle gesture
            if not self.paused:
                self.gesture.arm()

            # Dog click
            if not self.paused and self.settings.get("interactive.excited_on_click"):
                old_state = self.state
                self.state = State.EXCITED
                self.tongue = True
                self.state_frames = 75
                self.bounce_val = 0.0
                self.bubbles.clear()
                self.returning = False
                self.task_phase = 0
                self.task_frames = 0
                self.stretch_factor = 0.0
                if old_state == State.RETURNING_BALL:
                    self.ball_x = float(self.ball_cx)
                    self.ball_visible = True

        elif event.button() == Qt.RightButton:
            self._show_menu(event.globalPos())

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        lx = event.pos().x()
        ly = event.pos().y()
        k = self.art_scale
        # Leave the ball and bowl to the single-click handlers
        if abs(lx - self.ball_cx) < int(12 * k) and ly > WIN_H - int(20 * k):
            return
        if abs(lx - self.bowl_cx) < int(13 * k) and ly > WIN_H - int(14 * k):
            return
        if (not self.paused and self.state != State.CLIMBING
                and self.settings.get("command.beg")):
            self._start_beg()

    def _add_toggle(self, menu, label, key):
        """Checkable menu action wired to a persisted behavior switch."""
        a = QAction(label, self)
        a.setCheckable(True)
        a.setChecked(self.settings.get(key))
        a.triggered.connect(lambda chk, k=key: self.settings.set(k, chk))
        menu.addAction(a)
        return a

    def _build_menu(self):
        menu = QMenu(self)

        a_pause = QAction("Pause animations", self)
        a_pause.setCheckable(True)
        a_pause.setChecked(self.paused)
        a_pause.triggered.connect(lambda chk: setattr(self, "paused", chk))
        menu.addAction(a_pause)

        a_start = QAction("Launch at startup", self)
        a_start.setCheckable(True)
        a_start.setChecked(self.startup_enabled)
        a_start.triggered.connect(self._handle_startup)
        menu.addAction(a_start)

        # Art: which renderer (kit) draws the dog, and how big everything is.
        # Groups + actions are parented to the (transient) submenu so they're
        # destroyed with it instead of piling up on the widget per right-click.
        m_art = menu.addMenu("Art")
        kit_group = QActionGroup(m_art)
        kit_choices = [("procedural", "Classic shapes (procedural)")]
        kit_choices += [(name, "Pixel-art sprites" if name == "pixel"
                         else f"Sprites: {name}")
                        for name in self.sprite_kits]
        for kit, label in kit_choices:
            a = QAction(label, m_art)
            a.setCheckable(True)
            a.setChecked(self.art_kit == kit)
            a.setActionGroup(kit_group)
            a.triggered.connect(lambda chk, n=kit: self._set_art_kit(n))
            m_art.addAction(a)
        m_art.addSeparator()
        size_group = QActionGroup(m_art)
        for label, val in (("Size: small (75%)", 0.75),
                           ("Size: normal (100%)", 1.0),
                           ("Size: large (125%)", 1.25),
                           ("Size: extra large (150%)", 1.5),
                           ("Size: huge (200%)", 2.0)):
            a = QAction(label, m_art)
            a.setCheckable(True)
            a.setChecked(abs(self.art_scale - val) < 1e-6)
            a.setActionGroup(size_group)
            a.triggered.connect(lambda chk, v=val: self._set_art_scale(v))
            m_art.addAction(a)

        menu.addSeparator()
        menu.addSection("Behaviors")

        m_idle = menu.addMenu("Idle")
        self._add_toggle(m_idle, "Fidgets while lying", "idle.fidgets_lying")
        self._add_toggle(m_idle, "Fidgets while standing", "idle.fidgets_standing")
        self._add_toggle(m_idle, "Wander walk", "idle.wander_walk")
        self._add_toggle(m_idle, "Scratch", "idle.scratch")
        self._add_toggle(m_idle, "Chew bone", "idle.chew")
        self._add_toggle(m_idle, "Sniff walk", "idle.sniff_walk")
        self._add_toggle(m_idle, "Zoomies (rare)", "idle.zoomies")

        m_timed = menu.addMenu("Timed")
        self._add_toggle(m_timed, "Stretch reminders", "timed.stretch_reminders")
        self._add_toggle(m_timed, "Water reminders", "timed.water_reminders")

        m_inter = menu.addMenu("Interactive")
        self._add_toggle(m_inter, "Alert when cursor is near", "interactive.cursor_alert")
        self._add_toggle(m_inter, "Excited when clicked", "interactive.excited_on_click")
        self._add_toggle(m_inter, "Fetch the ball", "interactive.fetch_ball")

        m_cmd = menu.addMenu("Command")
        self._add_toggle(m_cmd, "Roll over (click, then circle the dog 3x)",
                         "command.roll_over")
        self._add_toggle(m_cmd, "Beg (double-click the dog)", "command.beg")

        m_react = menu.addMenu("Reactive")
        self._add_toggle(m_react, "Greet on launch / your return",
                         "reactive.greet")
        self._add_toggle(m_react, "Climb up on launch",
                         "reactive.startup_climb")

        menu.addSeparator()
        menu.addSection("Test")
        for label, handler in (("Test: stretch", self._test_stretch),
                               ("Test: water reminder", self._test_water),
                               ("Test: fetch", self._test_fetch),
                               ("Test: scratch", self._test_scratch),
                               ("Test: chew bone", self._test_chew),
                               ("Test: sniff walk", self._test_sniff),
                               ("Test: roll over", self._test_roll_over),
                               ("Test: bark", self._test_bark),
                               ("Test: beg", self._test_beg),
                               ("Test: greet", self._test_greet),
                               ("Test: zoomies", self._test_zoomies),
                               ("Test: climb up", self._test_climb)):
            a = QAction(label, self)
            a.triggered.connect(handler)
            menu.addAction(a)

        menu.addSeparator()

        # === DEBUG HUD (dev tool — delete this block to remove) ===
        a_hud = QAction("Debug: show state HUD", self)
        a_hud.setCheckable(True)
        a_hud.setChecked(getattr(self, "hud_enabled", False))
        a_hud.triggered.connect(self._toggle_hud)
        menu.addAction(a_hud)
        # === end DEBUG HUD ===

        a_quit = QAction("Quit", self)
        a_quit.triggered.connect(QApplication.quit)
        menu.addAction(a_quit)
        return menu

    def _show_menu(self, pos):
        self._build_menu().exec_(pos)

    # === DEBUG HUD (dev tool — delete this method to remove) ===
    def _toggle_hud(self, checked):
        self.hud_enabled = checked
        self.settings.set("debug.hud", checked)
        if self._hud is not None:
            if checked:
                self._hud.show()
                self._hud.refresh(self)
            else:
                self._hud.hide()
    # === end DEBUG HUD ===

    def _handle_startup(self, checked):
        self.startup_enabled = checked
        self._write_startup(checked)

    # ── helper ───────────────────────────────────────────────────────────────

    def _walk_toward(self, dest):
        """Move dog one step toward dest at the current gait. True = arrived."""
        g = self._active_gait()
        speed = g.speed if g is not None else GAITS["trot-brisk"].speed
        diff = dest - self.dog_sx
        if abs(diff) < 2.0 or abs(diff) <= speed:
            self.dog_sx = float(dest)
            return True
        self.facing = 1 if diff > 0 else -1
        self.dog_sx += speed * self.facing
        return abs(self.dog_sx - dest) < 2.0

    def _check_pending(self):
        """Consume pending reminder flags when not already running a task."""
        if self.state in (State.FETCHING, State.RETURNING_BALL,
                          State.STRETCHING, State.DRINKING, State.TASK_RETURN,
                          State.ROLL_OVER, State.BARKING, State.BEG,
                          State.GREETING, State.CLIMBING):
            return
        if self.stretch_pending:
            self.stretch_pending = False
            if self.settings.get("timed.stretch_reminders"):
                self.bubbles.clear()
                self._sleep_timer.stop()
                self.returning = False
                self.state = State.STRETCHING
                self.task_phase = 0
                self.task_frames = 0
                self.stretch_factor = 0.0
            return
        if self.water_pending:
            self.water_pending = False
            if self.settings.get("timed.water_reminders"):
                self.bubbles.clear()
                self._sleep_timer.stop()
                self.returning = False
                self.state = State.DRINKING
                self.task_phase = 0
                self.task_frames = 0
            return

    # ── task state updates ────────────────────────────────────────────────────

    def _update_fetching(self):
        if self.task_phase == 0:
            if self._walk_toward(self.ball_x):
                self.ball_visible = False
                self.task_phase = 1
                self.task_frames = 15
        elif self.task_phase == 1:
            self.task_frames -= 1
            if self.task_frames <= 0:
                self.state = State.RETURNING_BALL
                self.task_phase = 0

    def _update_returning_ball(self):
        if self._walk_toward(self.bed_cx):
            self.ball_x = float(self.ball_cx)
            self.ball_visible = True
            self.state = State.SLEEPING
            self.facing = -1
            self._arm_sleep_timer()

    def _update_stretching(self):
        self.task_frames += 1
        self.stretch_factor = math.sin(math.pi * min(self.task_frames, 90) / 90)
        if self.task_frames >= 90:
            self.stretch_factor = 0.0
            self.task_frames = 0
            if abs(self.dog_sx - self.bed_cx) < 3:
                self.dog_sx = float(self.bed_cx)
                self.state = State.SLEEPING
                self.facing = -1
                self._arm_sleep_timer()
            else:
                self.state = State.TASK_RETURN

    def _update_drinking(self):
        if self.task_phase == 0:
            drink_pos = float(self.bowl_cx - int(20 * self.art_scale))
            if self._walk_toward(drink_pos):
                self.dog_sx = drink_pos
                self.facing = 1
                self.task_phase = 1
                self.task_frames = 0
        elif self.task_phase == 1:
            self.task_frames += 1
            duration = 80 if self.bowl_full else 30
            if self.task_frames >= duration:
                if self.bowl_full:
                    self.bowl_full = False
                self.task_frames = 0
                self.task_phase = 0
                self.state = State.TASK_RETURN

    def _update_task_return(self):
        if self._walk_toward(self.bed_cx):
            self.dog_sx = float(self.bed_cx)
            self.state = State.SLEEPING
            self.facing = -1
            self._arm_sleep_timer()

    # ── roll-over command ─────────────────────────────────────────────────────

    def _start_roll_over(self):
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0
        self.task_frames = 0
        # ~3.5 s procedurally; the sprite clip's own length when one is active
        self.state_frames = self._one_shot_ticks("roll-over", 75)
        self.tongue = False
        self.bounce_val = 0.0
        self.state = State.ROLL_OVER

    def _update_roll_over(self):
        self.task_frames += 1
        if self.task_frames >= self.state_frames:
            self.task_frames = 0
            self.state = State.SLEEPING
            self.facing = -1
            self._arm_sleep_timer()

    # ── bark / beg / greet / zoomies ──────────────────────────────────────────

    def _start_bark(self):
        """Short head-back bark. Fired by greet today; the Phase 4c window
        detector will call this too (see docs/PHASE-4-HOOKS-DESIGN.md)."""
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0
        self.task_frames = 0
        self.state_frames = self._one_shot_ticks("bark", 26)   # ~1.2 s
        self.state = State.BARKING

    def _update_barking(self):
        self.task_frames += 1
        if self.task_frames >= self.state_frames:
            self.task_frames = 0
            self.state = State.SLEEPING
            self.facing = -1
            self._arm_sleep_timer()

    def _start_beg(self):
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0
        self.task_frames = 0
        self.state_frames = self._one_shot_ticks("beg-sit-up", 50)  # ~2.4 s
        self.tongue = False
        self.bounce_val = 0.0
        self.state = State.BEG

    def _update_beg(self):
        self.task_frames += 1
        if self.task_frames >= self.state_frames:
            self.task_frames = 0
            self.state = State.SLEEPING
            self.facing = -1
            self._arm_sleep_timer()

    def _launch_greet(self):
        self._maybe_greet()

    def _maybe_greet(self):
        """Greet if switched on and the dog is just resting."""
        if self.paused or not self.settings.get("reactive.greet"):
            return
        if self.state not in (State.SLEEPING, State.ALERT):
            return
        self._last_greet_t = time.monotonic()
        self._start_greet()

    def _start_greet(self):
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0
        self.task_frames = 0
        self.state_frames = 55              # ~2.6 s of hops + wag
        self._greet_bark = random.random() < 0.5
        self.state = State.GREETING

    def _update_greeting(self):
        self.task_frames += 1
        self.bounce_val = abs(math.sin(self.task_frames * 0.35)) * 5
        if self.task_frames >= self.state_frames:
            self.bounce_val = 0.0
            self.task_frames = 0
            if self._greet_bark:
                self._greet_bark = False
                self._start_bark()          # finish the hello with a bark
            else:
                self.state = State.SLEEPING
                self.facing = -1
                self._arm_sleep_timer()

    def _set_zoom_bounds(self):
        """Dash endpoints, derived from the (scale-dependent) bed position so
        the run always clears the corner. Recomputed if the scale changes."""
        self.zoom_left = max(self.walk_min, self.bed_cx - 450)
        self.zoom_right = self.bed_cx - int(80 * self.art_scale)

    def _start_zoomies(self):
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0                 # dashes completed
        self.task_frames = 0
        self.state_frames = random.randint(3, 5)   # total dashes
        self._set_zoom_bounds()
        self.zoom_dest = self.zoom_left
        self.state = State.ZOOMIES

    def _update_zoomies(self):
        if self._walk_toward(self.zoom_dest):
            self.task_phase += 1
            if self.task_phase >= self.state_frames:
                self.task_phase = 0
                self.state = State.TASK_RETURN      # plod home, spent
                return
            self.zoom_dest = (self.zoom_right
                              if abs(self.zoom_dest - self.zoom_left) < 1.0
                              else self.zoom_left)

    # ── startup climb ─────────────────────────────────────────────────────────

    def _start_climb(self):
        """Haul up from behind the taskbar like a ledge (launch sequence)."""
        # Only the launch path re-arms this immediately after; a Test-menu or
        # any other climb stays inert with respect to the greet chain.
        self._climb_then_greet = False
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0
        self.task_frames = 0
        self.state_frames = self._one_shot_ticks("climb-up", 80)   # ~2.6 s
        self.tongue = False
        self.bounce_val = 0.0
        self.facing = -1
        self.state = State.CLIMBING

    def _update_climbing(self):
        self.task_frames += 1
        if self.task_frames >= self.state_frames:
            self.task_frames = 0
            self.state = State.SLEEPING
            self.facing = -1
            self._arm_sleep_timer()
            if self._climb_then_greet:
                self._climb_then_greet = False
                self._greet_timer.start(700)   # topped out — now say hello

    # ── idle behaviour updates ────────────────────────────────────────────────

    def _update_scratching(self):
        self.task_frames += 1
        if self.task_frames >= self.state_frames:
            self.task_frames = 0
            self.state = State.SLEEPING
            self.facing = -1
            self._arm_sleep_timer()

    def _update_chewing(self):
        self.task_frames += 1
        if self.task_frames >= self.state_frames:
            self.task_frames = 0
            self.state = State.SLEEPING
            self.facing = -1
            self._arm_sleep_timer()

    def _update_sniff_walk(self):
        if self.task_phase == 0:                        # walking slowly
            diff = self.sniff_dest - self.dog_sx
            if abs(diff) < 2:
                self.dog_sx = float(self.sniff_dest)
                self.task_phase = 0
                self.task_frames = 0
                self.state = State.TASK_RETURN
                return
            self.facing = 1 if diff > 0 else -1
            self.dog_sx += GAITS["sniff-walk"].speed * self.facing
            # Trigger a sniff-pause when crossing the next pause point
            if self.facing == -1 and self.dog_sx <= self.sniff_next_pause:
                self.task_phase = 1
                self.task_frames = random.randint(12, 18)   # ~0.5 s
            elif self.facing == 1 and self.dog_sx >= self.sniff_next_pause:
                self.task_phase = 1
                self.task_frames = random.randint(12, 18)
        else:                                           # paused, sniffing
            self.task_frames -= 1
            if self.task_frames <= 0:
                self.task_phase = 0
                # Schedule next pause point further along
                self.sniff_next_pause = (self.dog_sx
                                         + self.facing * random.randint(20, 30))

    # ── idle behaviour drawing ────────────────────────────────────────────────

    def _draw_scratch_leg(self, p, cx, base, f, DARK, frames=None):
        """Kicking back leg for the scratch animation (state or fidget)."""
        if frames is None:
            frames = self.task_frames
        kick = math.sin(frames * 0.85)                 # rapid oscillation
        # Back hip is on the opposite side from the head
        hip_x = int(cx - f * 14)
        hip_y = base - 8
        # Leg swings in the facing direction (toward the ear/neck)
        extent = max(0.0, kick) * 22
        tip_x = int(hip_x + f * extent)
        tip_y = int(hip_y - (5 + max(0.0, kick) * 14))
        p.setPen(QPen(DARK, 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(hip_x, hip_y, tip_x, tip_y)

    def _draw_bone(self, p, cx, base, f, head_bob):
        """Bone held in dog's mouth during CHEWING."""
        BONE = QColor(238, 220, 182)
        bw = 52; bh = 17; leg_len = 17
        body_bottom = base - leg_len
        body_top    = body_bottom - bh
        hcx = cx + f * (bw // 2 - 2)
        hcy = body_top - 4 + head_bob
        # Centre the bone in front of the mouth
        bcx = int(hcx + f * 20)
        bcy = int(hcy + 4)
        shaft_w = 12; shaft_h = 4; knob_w = 6; knob_h = 8
        p.setPen(Qt.NoPen)
        p.setBrush(BONE)
        p.drawRoundedRect(bcx - shaft_w // 2, bcy - shaft_h // 2,
                          shaft_w, shaft_h, 2, 2)
        p.drawEllipse(bcx - shaft_w // 2 - knob_w // 2, bcy - knob_h // 2,
                      knob_w, knob_h)
        p.drawEllipse(bcx + shaft_w // 2 - knob_w // 2, bcy - knob_h // 2,
                      knob_w, knob_h)

    def _draw_rollover(self, p, cx, base, f, BROWN, DARK, BLACK):
        """ROLL_OVER: brief settle, belly-up with paddling paws, right itself."""
        prog = self.task_frames / max(1, self.state_frames)

        if prog < 0.16 or prog >= 0.84:
            # Rolling down / righting itself: the lying pose with a wobble
            jx = int(math.sin(self.task_frames * 0.8) * 2)
            self._draw_sleeping(p, cx + jx, base, f, BROWN, DARK, BLACK)
            return

        # On the back, belly up
        bw, bh = 60, 20
        body_top = base - bh
        p.setPen(Qt.NoPen)
        p.setBrush(BROWN)
        p.drawEllipse(cx - bw // 2, body_top, bw, bh)
        # Belly patch
        p.setBrush(QColor(222, 168, 110))
        p.drawEllipse(cx - bw // 2 + 10, body_top + 2, bw - 20, bh - 8)

        # Paws paddling in the air
        p.setBrush(DARK)
        for i, lo in enumerate((-18, -7, 7, 18)):
            paddle = math.sin(self.task_frames * 0.45 + i * 1.4) * 3
            leg_h = 13 + int(paddle)
            p.drawRoundedRect(cx + lo - 2, body_top - leg_h, 5, leg_h, 2, 2)

        # Head lolling to the front side, upside-down-ish
        hr = 12
        hcx = cx + f * (bw // 2 + 2)
        hcy = base - 10
        p.setBrush(BROWN)
        p.drawEllipse(int(hcx - hr), int(hcy - hr), hr * 2, hr * 2)
        # Flopped ear
        p.setBrush(DARK)
        p.drawEllipse(int(hcx - f * 2 - 4), int(hcy - 2), 9, 12)
        # Closed eye (upside-down arc) + nose low
        p.setPen(QPen(BLACK, 1.5, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(int(hcx + f * 3 - 4), int(hcy - 2), 8, 6, 0, 180 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(BLACK)
        p.drawEllipse(int(hcx + f * 8 - 3), int(hcy + 4), 7, 5)

        # Tail curled at the rear
        tx = cx - f * (bw // 2 - 2)
        p.setPen(QPen(DARK, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        tp = QPainterPath()
        tp.moveTo(tx, base - 6)
        tp.quadTo(tx - f * 10, base - 12, tx - f * 6, base - 18)
        p.drawPath(tp)

    def _draw_bark_mouth(self, p, cx, base, f, head_bob):
        """Open mouth for the bark, at the standing pose's muzzle position."""
        bw = 52; bh = 17; leg_len = 17
        body_bottom = base - leg_len
        body_top = body_bottom - bh
        hcx = cx + f * (bw // 2 - 2)
        hcy = body_top - 4 + head_bob
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(55, 28, 18))
        p.drawEllipse(int(hcx + f * 7 - 3), int(hcy + 6), 7, 6)

    def _draw_beg(self, p, cx, base, f, BROWN, DARK, BLACK, WHITE, PINK):
        """BEG: rear stays planted, torso tilts up, front paws dangle."""
        prog = self.task_frames / max(1, self.state_frames)
        if prog < 0.2:
            lift = prog / 0.2
        elif prog > 0.85:
            lift = (1.0 - prog) / 0.15
        else:
            lift = 1.0

        bw, bh, leg_len = 52, 17, 17
        body_bottom = base - leg_len + int(lift * 6)   # haunches sink a little
        body_top = body_bottom - bh

        # Rear legs planted on the ground, folding shorter as the rear sinks
        p.setPen(Qt.NoPen)
        p.setBrush(DARK)
        rear = (-18, -6) if f > 0 else (8, 20)
        for lx in rear:
            p.drawRoundedRect(int(cx + lx - 2), body_bottom - 1, 5,
                              int(base - body_bottom + 1), 2, 2)

        # Body tilts up around the rear hip
        th = math.radians(lift * 38)
        pivot_x = cx - f * (bw // 2 - 8)
        p.setBrush(BROWN)
        p.save()
        p.translate(pivot_x, body_bottom)
        p.rotate(-f * lift * 38)
        p.translate(-pivot_x, -body_bottom)
        p.drawEllipse(cx - bw // 2, body_top, bw, bh)
        p.restore()

        # Head rides the raised front end of the body
        hr = 13
        reach = bw - 10
        hcx = pivot_x + f * reach * math.cos(th)
        hcy = body_bottom - reach * math.sin(th) - 10
        p.setBrush(BROWN)
        p.drawEllipse(int(hcx - hr), int(hcy - hr), hr * 2, hr * 2)
        p.setBrush(DARK)
        p.drawEllipse(int(hcx - f * 2 - 5), int(hcy - hr - 2), 9, 14)
        p.setBrush(BLACK)
        p.drawEllipse(int(hcx + f * 4 - 3), int(hcy - 7), 6, 6)
        p.setBrush(WHITE)
        p.drawEllipse(int(hcx + f * 4 - 1), int(hcy - 6), 2, 2)
        p.setBrush(BLACK)
        p.drawEllipse(int(hcx + f * 9 - 3), int(hcy + 1), 7, 5)
        if lift > 0.8:
            p.setBrush(PINK)
            p.drawEllipse(int(hcx + f * 8 - 3), int(hcy + 7), 6, 7)

        # Front paws dangling below the chest, with a tiny paddle
        paddle = math.sin(self.task_frames * 0.3) * 1.5 * lift
        p.setBrush(DARK)
        chest_x = pivot_x + f * (reach - 16) * math.cos(th)
        chest_y = body_bottom - (reach - 16) * math.sin(th)
        p.drawRoundedRect(int(chest_x - f * 1 - 2), int(chest_y + paddle),
                          5, 11, 2, 2)
        p.drawRoundedRect(int(chest_x + f * 7 - 2), int(chest_y - paddle),
                          5, 11, 2, 2)

        # Tail resting on the ground behind, slow sweep
        sweep = math.sin(self.tail_phase * 0.6) * 4
        tx = pivot_x - f * 4
        p.setPen(QPen(DARK, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        tp = QPainterPath()
        tp.moveTo(tx, body_bottom + 6)
        tp.quadTo(tx - f * 10, body_bottom + 2 - sweep, tx - f * 16,
                  body_bottom + 4 - sweep)
        p.drawPath(tp)

    def _draw_climb(self, p, cx, base, f, BROWN, DARK, BLACK, WHITE, PINK):
        """CLIMBING: haul up over the taskbar edge like a ledge.

        Procedural placeholder — the pixel-art kit has no climb-up clip yet
        (open art item; _sprite_draw picks it up automatically once a clip
        named "climb-up" lands in the manifest). Anything drawn below
        DOG_BASE is clipped at the window edge, which reads as "still behind
        the taskbar".
        """
        prog = self.task_frames / max(1, self.state_frames)
        edge = DOG_BASE

        if prog < 0.45:
            # Two front paws hook over the edge; the head pulls up behind
            # them with little effort-bobs.
            t = prog / 0.45
            p.setPen(Qt.NoPen)
            p.setBrush(DARK)
            for px_off in (-10, 6):
                p.drawRoundedRect(cx + px_off, edge - 5, 6, 7, 2, 2)
            bob = math.sin(self.task_frames * 0.45) * 2.5 * (1.0 - t)
            hr = 13
            hcx = cx - f * 2
            hcy = edge + 14 - t * 24 + bob
            p.setBrush(BROWN)
            p.drawEllipse(int(hcx - hr), int(hcy - hr), hr * 2, hr * 2)
            p.setBrush(DARK)
            p.drawEllipse(int(hcx - f * 2 - 5), int(hcy - hr + 1), 9, 14)
            p.setBrush(BLACK)
            p.drawEllipse(int(hcx + f * 4 - 3), int(hcy - 7), 6, 6)
            p.setBrush(WHITE)
            p.drawEllipse(int(hcx + f * 4 - 1), int(hcy - 6), 2, 2)
            p.setBrush(BLACK)
            p.drawEllipse(int(hcx + f * 9 - 3), int(hcy + 1), 7, 5)
        elif prog < 0.85:
            # Body hauls up; legs scrabble (the walking swing reads as
            # scrambling for purchase while the body is still half-hidden).
            t = (prog - 0.45) / 0.40
            body_drop = int((1.0 - t) * 50)
            self._draw_standing(p, cx, base + body_drop, f, BROWN, DARK,
                                BLACK, WHITE, PINK, True, False, False,
                                head_bob=-3)
        else:
            # Up — settle with a quick little shake before resting.
            jx = int(math.sin(self.task_frames * 1.15) * 2)
            self._draw_standing(p, cx + jx, base, f, BROWN, DARK, BLACK,
                                WHITE, PINK, False, False, True)

    # ── fetch / bowl ──────────────────────────────────────────────────────────

    def _throw_ball(self):
        min_x = int(self.walk_min)
        max_x = int(self.bed_cx) - int(70 * self.art_scale)
        if max_x <= min_x:
            return
        self.ball_x = float(random.randint(min_x, max_x))
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.state = State.FETCHING
        self.task_phase = 0
        self.task_frames = 0
        self.returning = False

    def _refill_bowl(self):
        self.bowl_full = True

    # ── reminder timers ───────────────────────────────────────────────────────

    def _on_stretch_timer(self):
        self.stretch_pending = True

    def _on_water_timer(self):
        self.water_pending = True

    # ── dev test triggers ─────────────────────────────────────────────────────

    def _test_stretch(self):
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0
        self.task_frames = 0
        self.stretch_factor = 0.0
        self.state = State.STRETCHING

    def _test_water(self):
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0
        self.task_frames = 0
        self.state = State.DRINKING

    def _test_fetch(self):
        min_x = int(self.walk_min)
        max_x = int(self.bed_cx) - int(70 * self.art_scale)
        if max_x <= min_x:
            return
        self.ball_x = float(random.randint(min_x, max_x))
        self.ball_visible = True
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.state = State.FETCHING
        self.task_phase = 0
        self.task_frames = 0
        self.returning = False

    def _test_scratch(self):
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0
        self.task_frames = 0
        self.state_frames = random.randint(90, 120)
        self.state = State.SCRATCHING

    def _test_chew(self):
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0
        self.task_frames = 0
        self.state_frames = random.randint(240, 300)
        self.state = State.CHEWING

    def _test_roll_over(self):
        self._start_roll_over()

    def _test_bark(self):
        self._start_bark()

    def _test_beg(self):
        self._start_beg()

    def _test_greet(self):
        self._start_greet()

    def _test_zoomies(self):
        self._start_zoomies()

    def _test_climb(self):
        self._start_climb()

    def _test_sniff(self):
        self.bubbles.clear()
        self._sleep_timer.stop()
        self.returning = False
        self.task_phase = 0
        self.task_frames = 0
        sniff_dist = random.randint(100, 400)
        self.sniff_dest = max(self.walk_min, self.dog_sx - sniff_dist)
        self.sniff_next_pause = self.dog_sx - random.randint(20, 30)
        self.facing = -1
        self.state = State.SNIFF_WALK

    # ── startup registry ──────────────────────────────────────────────────────

    def _exe_path(self):
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'

    def _check_startup(self):
        key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key)
            winreg.QueryValueEx(k, "Biscuit")
            winreg.CloseKey(k)
            return True
        except Exception:
            return False

    def _write_startup(self, enable):
        key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE)
            if enable:
                winreg.SetValueEx(k, "Biscuit", 0, winreg.REG_SZ, self._exe_path())
            else:
                try:
                    winreg.DeleteValue(k, "Biscuit")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(k)
        except Exception as e:
            print(f"Registry error: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Biscuit()
    sys.exit(app.exec_())
