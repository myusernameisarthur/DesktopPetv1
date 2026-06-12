# Persi — Roadmap to the Full Vision

From where we are today to a finished, distributable desktop dog: every behavior, the
variability that makes it feel alive, the OS-level plumbing the new behaviors need, and the swap
from procedural drawing to real Persi art.

Read with `persi-behavior-animation-map.md` (the idle layer detail) and the
`transparent-desktop-app` skill (the build discipline).

---

## The vision in one paragraph

Persi is a dachshund that lives on the Windows taskbar and feels like a real pet: mostly asleep,
occasionally fidgeting, reacting to what you do (cursor, clicks, typing, opening windows),
obeying a couple of commands, and rendered in real hand-drawn art rather than procedural shapes.
Every behavior can be switched on or off. It ships as a signed exe that starts with Windows.

---

## Where we are now (Phase 0, done)

- Working POC: transparent click-through taskbar overlay, 12 states, procedural drawing.
- `transparent-desktop-app` skill installed and reconciled to the real code.
- Debug HUD live: shows STATE, ANIM, PHASE, FACING, time-in-state, next behavior.
- Git safety: `v1-poc` tag (restore point), `main` holds the skill, HUD on `feature/debug-hud`.
- Known constraint: two base poses (lying, standing) and one `trot` drive everything. Liveliness
  is capped until we add the idle layer, gaits, and real art.

---

## Guiding principles

1. One base pose set, many layers. Add fidgets, gaits, and props on top of lying/standing
   rather than authoring a full animation per action.
2. Variability over volume. Irregular timing and no-repeat memory make a few animations feel
   like many.
3. Every behavior is toggleable. A single settings store, one switch per behavior, persisted.
4. The HUD is the instrument. Every new behavior shows up there before we judge it.
5. One branch per phase, verified with the HUD, exe rebuilt, before the next.
6. Art is last. Real sprites go in only once the behavior and animation list is frozen.

---

## Master behavior catalog

Categories: **Idle** (ambient, self-triggered), **Timed** (clock), **Interactive** (cursor/click),
**Command** (deliberate gesture), **Reactive** (system events), **Mode** (sustained, toggled).
Every row gets an on/off switch (Phase 2). "New" marks behaviors not yet built.

| Behavior | Category | Trigger | Animation | New? |
|----------|----------|---------|-----------|------|
| Sleep / breathe | Idle (default) | resting state | lying + breathing | no |
| Ear flick / nose twitch / tail twitch | Idle | random while lying | fidget delta on lying pose | new |
| Deep sigh | Idle | random while lying | bigger breath + z puff | new |
| Dream paw kick | Idle | random while lying | legs twitch | new |
| Eye crack | Idle | random while lying | eyelid opens then closes | new |
| Resettle | Idle | random while lying | shift and re-curl | new |
| Scratch | Idle | random + Test | lying, body jitter, leg kick | no |
| Stress shake | Idle | random while standing | the dry-off shake, brief | new |
| Bone from pocket + chew | Idle | random while standing | reach behind, produce bone, gnaw | new (extends Chew) |
| Blink / ear swivel / weight shift | Idle | random while standing | fidget delta on standing pose | new |
| Head tilt / look around | Idle | random while standing | head turns | new |
| Sit | Idle or Command | random, or future command | drop to sit, hold, stand | new |
| Stretch reminder | Timed | every 30 min | stretch + yawn (one-shot) | no |
| Water reminder | Timed | every 60 min | walk to bowl, drink, empties | no |
| Cursor proximity / alert | Interactive | cursor near | standing, ears up, faces cursor, wag | no (re-signature) |
| Excited | Interactive | left-click dog | bounce in place, tongue, fast wag | no |
| Fetch | Interactive | click ball | scamper to ball, return | no |
| Normal walk | Interactive/Idle | roam + return | brisk trot | no (new gait) |
| Sniff walk | Idle | random | slow nose-down walk, pauses | no (new gait) |
| Roll over | Command | click dog, then circle it 3x | roll onto back, paws up, righting | new |
| Beg | Command/Interactive | future gesture or click variant | sit up, paws up | new (optional) |
| Type-along | Mode | you start typing (mode on) | produces typewriter, types in time | new |
| Bark at new window | Reactive | a new top-level window opens | head-back bark, brief | new |
| Greet | Reactive | app launch / return from long idle | stand, wag, maybe a bark | new (optional) |
| Zoomies | Idle (rare) | rare random | fast back-and-forth dash | new (optional) |

---

## Phases

### Phase 1 — Idle micro-behavior engine + fidget catalogs ✅ DONE 2026-06-11 (see PHASE-1-REPORT.md)

Goal: idle Persi feels alive. Build the variability engine (irregular timing, weighting,
no-repeat memory, one-fidget-at-a-time) and the lying/standing fidget catalogs from the design
map, plus the three you added: stress shake, bone-from-pocket chew, and scratch folded into the
idle roll.

Deliverables: fidget engine module; lying fidgets (ear flick, nose twitch, tail twitch, sigh,
dream kick, eye crack, resettle); standing fidgets (blink, ear swivel, weight shift, head tilt,
look around, shake, bone-chew); HUD `FIDGET` line; ALERT given its own idle signature so it stops
reading like a paused walk.

Exit criteria: watching idle Persi for two minutes shows varied, non-repeating motion at a calm
rate, and the HUD confirms fidget variety.

### Phase 2 — Settings control board (every behavior toggleable) ✅ DONE 2026-06-11 (see PHASE-2-REPORT.md)

Goal: one switch per behavior, remembered between launches. This is foundational because every
later behavior plugs into it.

Deliverables: a settings store as JSON in `%APPDATA%\Persi\settings.json` (keeps "launch at
startup" in the registry as-is, or migrates it, your call); the right-click menu reorganized into
grouped, checkable toggles (Idle, Timed, Interactive, Command, Reactive, Modes), the existing
Test section, and the Debug HUD toggle; each behavior reads its switch before firing; defaults
defined per behavior.

Exit criteria: toggling any behavior off stops it firing, survives a restart, and the Test menu
still force-fires it for debugging regardless of the switch.

### Phase 3 — Distinct gaits ✅ DONE 2026-06-11 (see PHASE-3-REPORT.md)

Goal: kill the "six states, one trot" tell. Author at least brisk trot, plod, and scamper, and
route states to them (map in the design map, Part 3). Sniff-walk gets its slow nose-down gait.

Exit criteria: WALKING, FETCHING/RETURNING, TASK_RETURN, and SNIFF_WALK visibly differ in
motion, and the HUD shows ANIM changing with them.

### Phase 4 — Input and system enablers + their behaviors ⚠️ PARTIAL 2026-06-12: 4a (roll-over gesture) DONE; 4b/4c (keyboard + window hooks) deferred by owner decision — full design in PHASE-4-HOOKS-DESIGN.md

Goal: the plumbing for command gestures, type-along, and window-bark, then the behaviors on top.
This phase is gated by the risks below; treat each enabler as its own sub-branch.

**4a. Mouse-gesture recognition (roll over).** After a click on the dog, watch the cursor. If it
makes about three full loops around the dog's center within a short window, fire roll over (lie
back, paws up, a little wriggle, then right itself). Recognition: accumulate the change in angle
of the cursor around the dog center; about 3 x 360 degrees with consistent direction triggers it;
reset if the cursor wanders off or time runs out. Low OS risk (just cursor position).

**4b. Type-along mode.** When the mode is on and you begin typing, Persi produces a tiny
typewriter and types in rhythm with you, pausing when you pause, putting it away after you stop.
Enabler: a global keyboard listener that detects typing **activity only**. It must never store,
log, or transmit which keys you press; it reads "a key went down" and the rate, nothing more.
Medium-high OS risk: global keyboard hooks can trip antivirus and are privacy-sensitive, so this
behavior ships off by default with a clear in-app note about what it does and doesn't read.

**4c. Bark at new window.** When a new top-level application window opens, Persi gives a short
bark. Enabler: a Windows event hook (`SetWinEventHook` for window-create / foreground events via
ctypes) or a polled window-list diff. Must filter to real, visible, top-level windows so it
doesn't bark at every invisible helper window or tooltip, and rate-limit so a burst of windows
yields one bark, not ten. Medium OS risk: event hooks can be flagged; default this to off or to a
gentle rate.

Deliverables: gesture recognizer; roll over behavior; keyboard-activity detector + type-along
mode + typewriter prop; window-event detector + bark behavior; all three wired to Phase 2
toggles and shown on the HUD.

Exit criteria: each fires reliably from its real trigger, each has a working on/off switch, and
type-along and window-bark are documented as activity-only / filtered.

### Phase 5 — Remaining new behaviors ✅ DONE 2026-06-12 — behavior list FROZEN (see PHASE-5-REPORT.md + ANIMATION-INVENTORY.md)

Goal: round out character once the foundation reads as alive. From the catalog: beg, greet on
launch / return from long idle, zoomies (rare), and any others you want promoted from the design
map's Part 4. Each is a small behavior on the existing poses plus a flourish, wired to a toggle
and the HUD.

Exit criteria: behavior list is **frozen**. This freeze is the gate to art, per your rule.

### Phase 6 — Art and animation implementation (the visual leap)

Goal: replace procedural drawing with real Persi art. This is the largest single phase and
depends on the frozen behavior list, because the list defines exactly which animations need
frames.

Steps:
1. Build the animation inventory: from the frozen catalog, list every distinct animation and its
   frame count (idle fidgets, each gait, each one-shot, each prop like bone and typewriter).
2. Produce frames. Your saved art (`Persi-walk.png`, `Persi2-sleep.png`) is single stills, so each
   animation needs a frame sequence. Decide the production route: hand-drawn frames, AI-generated
   frames cleaned up, or a rig-and-render pipeline. This choice sets cost and timeline and is its
   own decision point.
3. Cut frames into spritesheets per the skill's spritesheet discipline (measure, never guess).
4. Build `assets.json` indexing every sprite and animation (skill: assets-and-behaviors).
5. Swap the renderer: replace the procedural `_draw_*` calls with frame playback driven by the
   same state machine and the same HUD. The state machine doesn't change; only what it draws does.
6. Re-tune timing to the real frames.

Exit criteria: Persi renders entirely from art, every behavior animates, the HUD still reports
correctly, and idle Persi reads as a real sleeping dog.

### Phase 7 — Polish and robustness

Goal: production quality. Multi-monitor and DPI correctness (overlay re-anchors on resolution and
monitor changes), taskbar position handling (bottom is done; consider top/left/right), performance
(repaint only the dirty region, watch idle CPU), first-run experience, and a clean settings panel.
Flip the Debug HUD default to off here.

Exit criteria: runs quietly for a full day across monitor changes with low idle CPU and no visual
glitches.

### Phase 8 — Packaging and distribution

Goal: someone other than you can install and run it. Code-sign the exe (removes most antivirus
flags, especially important given the keyboard and window hooks), build an installer, wire
launch-at-startup, and decide on an update path. Optional: a small landing page.

Exit criteria: a signed installer that a non-technical person installs, runs, and uninstalls
cleanly.

---

## Technical enablers and risks (read before Phase 4 and 8)

| Enabler | Used by | Risk | Mitigation |
|---------|---------|------|------------|
| Cursor-path angle tracking | Roll over gesture | Low | Pure math on cursor position; no OS hook |
| Global keyboard activity hook | Type-along | High: AV flags, privacy | Detect activity only, never log keys; off by default; in-app disclosure; sign the exe |
| Window event hook | Bark at new window | Medium: AV flags, noisy events | Filter to visible top-level windows; rate-limit; off or gentle by default; sign the exe |
| Settings store in AppData | All toggles | Low | JSON in `%APPDATA%\Persi`; never write inside the bundle |
| Code signing | Distribution | Cost, certificate setup | Budget a signing cert before Phase 8; it quiets the hooks' AV noise |

Privacy stance to state plainly in-app: Persi watches *that* you type and *that* windows open, to
react. It does not record what you type or read window contents.

---

## Art production: the decision that sets timeline

Phase 6 is gated by how frames get made. Three routes, to decide when the behavior list freezes:

- Hand-drawn: most control and character, slowest, needs an illustrator (you or hired).
- AI-generated then cleaned: fastest to volume, needs consistency work so every frame is the same
  dog, and a cleanup pass for transparent edges.
- Rig and render: draw Persi once as a puppet, pose and export frames; high setup, cheap variants
  after, good for many gaits and fidgets.

The number of distinct animations from Phases 1, 3, 4, 5 is the input to this. That's why art
comes after the freeze.

---

## Sequencing summary

```
Phase 0  done            POC + skill + HUD + git safety
Phase 1  done            fidgets, the life layer
Phase 2  done            every behavior toggleable
Phase 3  done            distinct locomotion
Phase 4  partial         gesture DONE; type-along + window-bark designed, deferred
Phase 5  done            beg, greet, zoomies, bark -> list FROZEN
Phase 6  art             frames, spritesheets, renderer swap
Phase 7  polish          multi-monitor, DPI, perf, HUD off
Phase 8  ship            sign, install, startup, update
```

---

## Open decisions for you

1. Idle feel and fidget rate: calm/subtle or busy/animated? Sets Phase 1 tuning.
2. `sit` and `beg`: idle fidgets, or proper command behaviors? Affects Phase 1 vs 5.
3. Type-along default: ship off (recommended, given the keyboard hook) and let you opt in?
4. Window-bark scope: every new app window, or only certain apps, and how gentle the rate?
5. Settings UI: keep it in the right-click menu, or graduate to a small settings window once the
   toggle count grows?
6. Art route (Phase 6): hand-drawn, AI-generated, or rig-and-render? Decide at the freeze, but
   worth forming a preference now since it shapes budget.
