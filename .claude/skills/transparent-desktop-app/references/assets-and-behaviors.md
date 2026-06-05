# Assets manifest and the behavior state machine

> **Reality check — the POC (`biscuit.py`) has no `assets.json` and no `Behavior`/`Scheduler`
> classes.** There are no art assets to index (the dog is procedural), so there is no manifest.
> Behaviors are not self-contained objects with `enter/update/exit`; they are values of a single
> `State` enum dispatched through one big `if/elif` chain inside the `Biscuit` QWidget. The §1
> manifest and §2 `Behavior`/`Scheduler` patterns are **aspirational refactors**, not the
> current code. §0 below is what actually runs.

---

## 0. How the POC's behavior system actually works

One `State` enum, one dispatch method, all inside `Biscuit`:

```python
class State(Enum):
    SLEEPING=0; ALERT=1; WALKING=2; EXCITED=3; FETCHING=4; RETURNING_BALL=5
    STRETCHING=6; DRINKING=7; TASK_RETURN=8; SCRATCHING=9; CHEWING=10; SNIFF_WALK=11
```

- **Default state = `SLEEPING` on the bed.** Almost everything ends by setting `state =
  SLEEPING`, `facing = -1`, and calling `_arm_sleep_timer()`.
- **Dispatch, not objects.** `_update_state()` is a `if self.state == State.WALKING: ... elif
  ...` chain that calls a `_update_<behavior>()` helper per state. Each helper mutates `self`
  and flips `self.state` when done. There is no scheduler and no `enter/exit`.
- **Ambient behavior is driven by a single-shot sleep timer, not a 20 s roll.**
  `_arm_sleep_timer()` schedules the next activity **4–8 minutes** out
  (`random.randint(4*60*1000, 8*60*1000)`). When it fires, `_start_walk()` picks one behavior
  with **equal weight**: `random.choice(('walk','scratch','chew','sniff'))` (unless a thrown
  ball is still out, in which case it fetches first). It is not the weighted ~80%-idle roll
  described in §2 — the "idle dominates" effect comes from the multi-minute sleep gap instead.
- **Reminder timers:** stretch every **30 min**, water every **60 min** (`_stretch_timer` /
  `_water_timer`). They set a `*_pending` flag that `_check_pending()` consumes on the next tick
  when no task is already running, so a reminder never interrupts a one-shot mid-play.
- **Cursor proximity = a real state transition, not just a passive modifier.** Within 150 px the
  dog faces the cursor and, if `SLEEPING`, switches to `ALERT`; it settles back to `SLEEPING`
  after a ~90-tick `cursor_settle` countdown once the cursor leaves.
- **One-shots use frame counters, not lock flags.** e.g. `SCRATCHING` runs until
  `task_frames >= state_frames`; `_check_pending()` simply refuses to start a reminder while one
  of those states is active, which is what makes them non-interruptible.
- **Input triggers** (in `mousePressEvent`): click dog → `EXCITED`; click ball at its corner →
  `_throw_ball()` → `FETCHING`; click bowl → `_refill_bowl()`.

---

## 1. assets.json — the single source of truth for art

Don't scatter frame sizes and file paths across the codebase. Declare them once. Loader code
reads this and nothing hard-codes a pixel dimension.

```json
{
  "sprites": {
    "dog": {
      "animations": {
        "sleep":   { "file": "dog_sleep.png",   "frame_w": 48, "frame_h": 32, "count": 4,  "fps": 4,  "loop": true,  "spacing": 0 },
        "breathe": { "file": "dog_breathe.png",  "frame_w": 48, "frame_h": 32, "count": 6,  "fps": 6,  "loop": true,  "spacing": 0 },
        "walk":    { "file": "dog_walk.png",     "frame_w": 56, "frame_h": 32, "count": 8,  "fps": 10, "loop": true,  "spacing": 0 },
        "sniff":   { "file": "dog_sniff.png",    "frame_w": 56, "frame_h": 32, "count": 8,  "fps": 5,  "loop": true,  "spacing": 0 },
        "scratch": { "file": "dog_scratch.png",  "frame_w": 48, "frame_h": 36, "count": 10, "fps": 12, "loop": false, "spacing": 0 },
        "chew":    { "file": "dog_chew.png",     "frame_w": 48, "frame_h": 32, "count": 6,  "fps": 8,  "loop": true,  "spacing": 0 },
        "stretch": { "file": "dog_stretch.png",  "frame_w": 64, "frame_h": 32, "count": 8,  "fps": 8,  "loop": false, "spacing": 0 },
        "drink":   { "file": "dog_drink.png",    "frame_w": 48, "frame_h": 32, "count": 6,  "fps": 8,  "loop": true,  "spacing": 0 },
        "excited": { "file": "dog_excited.png",  "frame_w": 48, "frame_h": 32, "count": 6,  "fps": 12, "loop": true,  "spacing": 0 }
      }
    }
  },
  "objects": {
    "bed":   { "file": "bed.png",   "anchor": "corner_bottom_right" },
    "bowl":  { "file": "bowl.png",  "states": { "full": "bowl_full.png", "empty": "bowl_empty.png" } },
    "ball":  { "file": "ball.png" }
  }
}
```

Frame sizes are **placeholders**; replace them with the measured values for the real art (see
sprites-and-animation.md). The point is the structure: one file maps every animation to its
spritesheet and timing.

### Build the manifest first

Before any window or behavior code, study `assets/` and write `assets.json`. This mirrors the
"create the manifest, then plan, then build" workflow and stops frame dimensions from leaking
into logic.

---

## 2. Behavior scheduler — default-idle + triggers

The pet rests in one **default state** (sleeping on the bed) most of the time and returns to it
after any behavior. Other behaviors fire from timers, user input, or weighted randomness. Only
one behavior runs at a time.

### Behavior as a small object

```python
class Behavior:
    name = "base"
    def enter(self, pet): ...        # set animation, start position, etc.
    def update(self, pet, dt): ...   # advance; return True when finished
    def exit(self, pet): ...         # cleanup; restore anything changed
```

Example: a walk that goes left across the taskbar and returns to the bed.

```python
class NormalWalk(Behavior):
    name = "walk"
    def enter(self, pet):
        pet.set_state("walk"); pet.facing = "left"; self.phase = "out"
        self.target_x = pet.bed_x - 300
    def update(self, pet, dt):
        speed = 40 * dt
        if self.phase == "out":
            pet.x -= speed
            if pet.x <= self.target_x:
                self.phase = "back"; pet.facing = "right"
        else:
            pet.x += speed
            if pet.x >= pet.bed_x:
                pet.x = pet.bed_x; return True   # done -> scheduler returns to idle
        return False
    def exit(self, pet):
        pet.set_state("sleep")
```

### The scheduler

```python
import random
from PyQt5.QtCore import QTimer, QElapsedTimer

class Scheduler:
    def __init__(self, pet):
        self.pet = pet
        self.current = None
        self.idle = SleepOnBed()        # default state
        self._enter(self.idle)
        self._clock = QElapsedTimer(); self._clock.start()
        t = QTimer(pet); t.timeout.connect(self._tick); t.start(16); self._t = t

        # timed behaviors
        self._add_timer(StretchReminder, minutes=30)
        self._add_timer(WaterReminder,   minutes=60)

        # ambient random roll every ~20s, heavily weighted to staying idle
        self._ambient = QTimer(pet); self._ambient.timeout.connect(self._maybe_wander)
        self._ambient.start(20_000)

    def _enter(self, beh):
        if self.current: self.current.exit(self.pet)
        self.current = beh; beh.enter(self.pet)

    def trigger(self, beh):
        # user/timer requested behavior; interrupt idle but not a locked one-shot
        if self.current is self.idle or self.current is None:
            self._enter(beh)

    def _tick(self):
        dt = self._clock.restart() / 1000.0
        if self.current and self.current is not self.idle:
            if self.current.update(self.pet, dt):
                self._enter(self.idle)        # finished -> back to default
        else:
            self.idle.update(self.pet, dt)

    def _maybe_wander(self):
        if self.current is not self.idle:
            return
        roll = random.random()
        if roll < 0.10:   self.trigger(NormalWalk())
        elif roll < 0.16: self.trigger(SniffWalk())
        elif roll < 0.20: self.trigger(Scratch())
        # ~80% of the time: stay asleep

    def _add_timer(self, behavior_cls, minutes):
        t = QTimer(self.pet)
        t.timeout.connect(lambda: self.trigger(behavior_cls()))
        t.start(minutes * 60_000)
```

Weights keep the default dominant (sleeping ~80%+ of the time), matching an unobtrusive pet.

### Input-driven behaviors

- **Click the sprite** -> `trigger(Excited())`
- **Click the ball** -> `trigger(Fetch())`
- **Water reminder** -> walk to bowl, drink, set bowl state to `empty`; clicking the bowl refills it
- **Right-click** -> open the settings menu (see packaging-and-testing.md)

Map clicks to regions in the overlay's mouse handler, then call `scheduler.trigger(...)`.

---

## 3. Cursor proximity

Conceptually a lightweight reaction: read the cursor x relative to the pet, set `facing`, and
react when the cursor is near. Keep it cheap; it runs every tick. **In the POC this is
implemented as an explicit `SLEEPING → ALERT → SLEEPING` transition** (150 px radius, ~90-tick
settle), not a passive modifier on an idle `update` — see §0.

---

## 4. Verify

- Let it run: the pet should rest in the default state and only occasionally do something.
- Fire each timed behavior via its test trigger (don't wait 30/60 min) and confirm it runs and
  returns to idle.
- Confirm one-shots can't be interrupted mid-play and looping behaviors can.
