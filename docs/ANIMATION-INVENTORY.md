# Animation Inventory — the FROZEN behavior list

Date frozen: 2026-06-12 (Phase 5 complete). This list is the input to Phase 6 (art): every
distinct animation the dog performs, with a suggested frame count for real sprite production.
Frame counts assume the taskbar scale (dog ≈ 100×75 px standing) and the app's effective
~21 ticks/s; loops list one cycle. "Layer" fidgets are small deltas on a base pose — with real
art each becomes a short overlay/replacement clip on the matching base.

Exceptions deliberately NOT frozen here: the two deferred hook behaviors (type-along's
`typewrite` + typewriter prop, window-bark reuses `bark`) are specified in
PHASE-4-HOOKS-DESIGN.md and add ONE new animation + one prop when built.

## Base poses & idle loops

| # | Animation | Used by | Type | Suggested frames |
|---|-----------|---------|------|------------------|
| 1 | breathing | SLEEPING | loop | 6 (gentle swell) |
| 2 | alert-stand | ALERT | loop | 4 (ears up, gentle sway) |
| 3 | bounce | EXCITED | loop | 6 (hop + tongue + fast wag) |
| 4 | greet-wag | GREETING | loop ~2.6 s | 6 (hops; can share cells with bounce) |

## Gaits (walk cycles)

| # | Animation | Used by | Type | Suggested frames |
|---|-----------|---------|------|------------------|
| 5 | trot-brisk | WALKING, DRINKING approach | loop | 8 |
| 6 | plod | TASK_RETURN | loop | 8 (head low, heavy) |
| 7 | plod-carry | RETURNING_BALL | loop | 8 (plod + ball in mouth; can be plod + prop overlay) |
| 8 | scamper | FETCHING | loop | 6 (short airborne strides) |
| 9 | sniff-walk | SNIFF_WALK | loop | 8 + 2 pause-sniff frames |
| 10 | dash | ZOOMIES | loop | 6 (stretched full-speed cycle) |

## One-shots

| # | Animation | Used by | Type | Suggested frames |
|---|-----------|---------|------|------------------|
| 11 | stretch | STRETCHING | one-shot ~4 s | 10 (rise, long stretch, yawn, settle) |
| 12 | drink | DRINKING at bowl | loop ~4 s | 6 (head-bob lapping) |
| 13 | scratch | SCRATCHING | loop 3–4 s | 8 (body jitter + leg kick) |
| 14 | chew | CHEWING | loop 8–10 s | 6 (gnaw cycle + bone prop) |
| 15 | roll-over | ROLL_OVER | one-shot ~3.5 s | 12 (roll on 3, paddle 6, right 3) |
| 16 | bark | BARKING (+ future window-bark) | one-shot ~1.2 s | 5 (head back, two bobs, open/close mouth) |
| 17 | beg-sit-up | BEG | one-shot ~2.4 s | 8 (sit up 3, hold/paddle 3, down 2) |

## Fidget layers — lying (on the `breathing` base)

| # | Fidget | Frames | | # | Fidget | Frames |
|---|--------|--------|---|---|--------|--------|
| 18 | ear-flick | 3 | | 22 | dream-kick | 4 |
| 19 | nose-twitch | 2 | | 23 | eye-crack | 3 |
| 20 | tail-twitch | 3 | | 24 | resettle | 6 |
| 21 | sigh (+z puff) | 4 | | 25 | scratch-lite | 4 (short kick burst) |

## Fidget layers — standing (on the `alert-stand` base)

| # | Fidget | Frames | | # | Fidget | Frames |
|---|--------|--------|---|---|--------|--------|
| 26 | blink | 2 | | 30 | look-around | 5 |
| 27 | ear-swivel | 3 | | 31 | wag-burst | 4 |
| 28 | weight-shift | 3 | | 32 | shake-off | 6 |
| 29 | head-tilt | 4 | | 33 | bone-chew (pocket) | 8 (reach 2, gnaw 4, stow 2) |
| | | | | 34 | sit | 6 (down 2, hold 2, up 2) |

## Props & ambient objects (static or 2-state unless noted)

| Prop | States/frames |
|------|---------------|
| bed | 1 |
| bowl | 2 (full / empty) |
| ball | 1 (+ shine), drawn at rest, thrown, carried |
| bone | 1 (shared by chew + bone-chew fidget) |
| zzz puffs | 1 glyph, animated procedurally (drift/fade can stay procedural) |
| typewriter (future, 4b) | 3–4 (idle, tap, carriage) — not frozen, see design doc |

## Totals

**34 frozen animations** (4 base/idle loops, 6 gaits, 7 one-shots, 17 fidget layers) +
5 props ≈ **190–200 distinct frames** at the suggested counts. Facing is mirrored in code
(sign-multiplied offsets today; pixmap mirroring with real art), so only one direction needs
drawing. Production-route decision (hand-drawn / AI-assisted / rig-and-render) is the Phase 6
gate — see persi-roadmap.md "Art production".
