# Persi — Behavior & Animation Design Map

The spec the skill builds from. Leads with the idle layer because Persi is asleep or standing
~80% of the time, so that's where perceived life is won or lost. Gaits and new behaviors are
outlined after, to build once the idle foundation reads as alive.

Design principle: keep one base pose set (lying, standing) and add **layers** on top, rather
than drawing a new full animation per action. Variability comes from small, irregular,
non-repeating motion, not from more states.

---

## Part 1 — Idle micro-behaviors (build first)

### The idea

A **fidget** is a short, small motion that plays *without changing the state*. The dog stays
SLEEPING, but its ear flicks. STATE doesn't move; the drawing gets a brief additive delta. One
fidget at a time. Fidgets never interrupt a real behavior and never fire during a locked
one-shot (stretch, scratch).

This is a layer over the existing `_draw_sleeping` / `_draw_standing`, not a replacement.

### Fidget catalog — lying pose (SLEEPING, and the resting end of STRETCHING)

| Fidget | What's drawn | Duration | Rarity |
|--------|--------------|----------|--------|
| ear flick | one ear rotates fast and settles | ~0.3s | common |
| nose twitch | nose/snout small quick shift | ~0.25s | common |
| tail twitch | tail tip flicks once | ~0.3s | common |
| deep sigh | one larger breath swell + a small "z" puff | ~1.2s | medium |
| dream paw kick | front/back legs twitch a few times (dreaming) | ~0.6s | medium |
| eye crack | one eyelid opens a sliver, then closes | ~0.5s | medium |
| resettle | body shifts a little and re-curls | ~1.0s | rare |
| roll-over | rolls to the other side, re-curls | ~1.4s | rare |

### Fidget catalog — standing pose (ALERT, and pre/post-walk pauses)

| Fidget | What's drawn | Duration | Rarity |
|--------|--------------|----------|--------|
| blink | eyes close and open | ~0.2s | common |
| ear swivel | ears rotate toward cursor | ~0.4s | common |
| weight shift | small body lean / paw lift | ~0.5s | common |
| head tilt | head cocks to one side, holds, returns | ~0.8s | medium |
| look around | head turns left, then right | ~1.0s | medium |
| tail wag burst | a few fast wags, then stop | ~0.7s | medium |
| shake off | the existing body-shake, brief | ~0.8s | rare |
| sit | drops to a sit, holds, stands again | ~1.5s | rare |

### Fixing the ALERT vs paused-walk confusion

ALERT currently reads like a frozen walk. Give ALERT its own idle signature: ears up and
swiveling, frequent blinks, occasional head tilt toward the cursor. Movement-paused states stay
plain. Now they read differently even when both are standing still.

---

## Part 2 — Variability mechanics (the engine, build with Part 1)

This engine is the reusable core. It drives idle fidgets now and behavior variants later.

### Irregular timing (the anti-metronome rule)

Don't fire fidgets on a fixed clock. Each idle second, roll for whether a fidget starts, at a
low rate, so gaps between fidgets vary naturally. A rough target: a fidget every 4 to 12 seconds
while idle, never on a fixed beat. Each fidget carries its own cooldown so the same one can't
repeat back to back.

### Weighting

Each fidget has a weight (common / medium / rare). Selection is weighted random over the
fidgets allowed in the current pose. Rare ones (roll-over, sit) surprise; common ones (blink,
ear flick) carry the baseline.

### No-repeat memory

Track the last 1 or 2 fidgets and exclude them from the next draw, so you never see the same
twitch twice in a row. Cheap, and it's most of what makes randomness *feel* random.

### Optional modulators (later, not v1)

- Energy / mood: a slow-drifting value that raises or lowers fidget rate (drowsy vs content).
- Time of day: fewer, slower fidgets late at night.
- Cursor distance: more standing fidgets when the cursor is near, fewer when far.

Mark these out of scope for the first build. The engine should expose a single rate multiplier
so they can hook in later without a rewrite.

### Show it on the HUD

Add one line so the new variability is legible (the reason you built the HUD):

```
STATE   sleeping
ANIM    breathing
FIDGET  ear-flick  0.2s        <- new line, blank when no fidget active
PHASE   inhale  3/6
...
```

Now you can watch fidget frequency and variety directly and tune the rates by eye.

---

## Part 3 — Distinct gaits (build second, outline only)

Split the single `trot` so locomotion reads per intent. Proposed mapping:

| Gait | States that use it | Feel |
|------|--------------------|------|
| brisk trot | WALKING (normal roam) | even, perky, medium speed |
| plod | TASK_RETURN, RETURNING_BALL | slower, heavier, "heading home" |
| scamper | FETCHING, EXCITED-moving | fast, bouncy, short strides |
| sniff-walk | SNIFF_WALK | slow, nose down, pause-and-go |
| approach | DRINKING approach phase | normal trot easing to a stop at the bowl |

Minimum worthwhile cut: brisk trot, plod, scamper. That alone breaks the "six states, one
animation" tell. Detail the leg timing per gait when we get here.

---

## Part 4 — New behaviors (build third, candidate list only)

Net-new actions to add once idle and gaits read well. To be cut and prioritized later:

beg (sit up, paws up), bark (head-back, small motion + optional none/sound), dig (front paws
scrabble), roll-over (full, as a behavior not just a fidget), follow-and-walk (trots alongside
the cursor for a bit), zoomies (rare burst of fast back-and-forth), greet (on app launch or
after long idle).

---

## Build order

1. Idle micro-behavior engine + the lying and standing fidget catalogs + HUD FIDGET line.
   Tune rates live until idle Persi feels alive.
2. Distinct gaits (brisk trot, plod, scamper at minimum).
3. New behaviors, prioritized from Part 4.

Each step is one branch, verified with the HUD, exe rebuilt, before the next.

---

## Open decisions for you

- Lying fidgets: any in the catalog you want cut or added? (e.g. keep roll-over as a rare fidget,
  or reserve it as a full behavior only?)
- Standing fidgets: is `sit` a fidget or a proper behavior with its own state?
- Target idle feel: subtle and calm, or busier and more animated? This sets the fidget rate.
