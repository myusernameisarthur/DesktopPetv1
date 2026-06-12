# Persi — Phase 6 Art Production Plan

Date: 2026-06-12. Route decided: **existing AI sprite sheets as source + Claude-built
pipeline**, pixel style, character locked to Persi (long-haired chocolate-and-tan dachshund).
Target: all 34 frozen animations + 5 props from `docs/ANIMATION-INVENTORY.md` (~190–200 frames).

## What the audit found

- `Persi-walk.png` — 5×5 grid, 256×256 tiles, 18 unique frames of a coherent walk cycle.
- `Persi2-sleep.png` — 5×5 grid, 21 unique lying/sleeping frames.
- `dog sprite.png` — 4 frames (1 lying, 3 standing) at ~200 px dog height equivalent.
- Dog content is ~200×128 px per tile on a flat green (71,112,76) background — keys out cleanly.
- The frames have **6,000+ distinct colors** — AI "pixel-style," not palette-locked pixel art.
  This is the root cause of the inconsistency you noticed. Fix: extract one master palette
  (~24 colors) from the best frames and quantize every frame to it. Same dog, every frame.
- The tile format (1280×1280, 5×5, green bg) matches PixelLab-style generators. If that's the
  tool, its "animate from reference character" mode is useful for Tier 3 below.

## Production tiers — how each animation gets made

**Tier 1 — slice and retime from existing sheets** (~40% of the set)
trot-brisk, plod, sniff-walk base, dash, scamper (speed/posture variants of the walk cycle),
breathing, and most lying fidgets (ear-flick, nose-twitch, resettle, eye-crack candidates are
already in the sleep sheet).

**Tier 2 — parts-based micro-edits** (~40%)
I decompose a master frame into layers (ears, tail, eyes, head, legs) and generate micro-
movements programmatically: blink, ear-swivel, tail-twitch, wag-burst, weight-shift, head-tilt,
look-around, sigh, scratch-lite, plod-carry (plod + ball overlay), sniff pause frames. Micro-
movements and transitions are exactly what this method is best at, and every output is
palette-locked by construction.

**Tier 3 — net-new poses** (~20%, the only risk area)
stretch, roll-over, beg-sit-up, drink, scratch, chew, bark, bounce/greet-wag, shake-off, sit.
Two paths, used per-animation depending on what review shows:
1. I build keyframes by pixel-editing recombined parts (attempted first, free).
2. If a result doesn't pass your review, you regenerate that one clip in your original tool —
   I give you the exact prompt + reference image + grid settings, the pipeline normalizes
   whatever comes back. ~10 minutes per clip on your side, max ~8 clips worst case.

**Props** — bed, bowl (2 states), ball, bone, zzz glyph: drawn directly at native resolution,
matched to the master palette. Small, low risk.

## Pipeline (I build and run all of it — `tools/art/`)

1. `slice.py` — cut grids, chroma-key green, trim, baseline-align every frame to a shared
   anchor (feet line) so animations don't bob when switching states.
2. `palette.py` — extract master palette, quantize all frames, report any frame that drifts.
3. `derive.py` — parts decomposition + Tier 2 generation.
4. `preview.py` — animated GIF per animation at real in-app timing (~21 ticks/s) →
   `OUTPUTS/persi-art/previews/`. **This is your review surface.**
5. `pack.py` — final spritesheets + a JSON manifest using the frozen inventory names/frame
   counts, native frame size 128×128 (dog ≈ 100×75 displayed, mirrored in code per roadmap).
6. Renderer swap in `biscuit.py` — replace procedural QPainter drawing with a pixmap frame
   player (manifest-driven, horizontal flip for facing). Procedural zzz drift stays procedural.

## Batches and review loop

| Batch | Contents | Source |
|-------|----------|--------|
| 0 | Pipeline + cleaned master frames + palette | audit done, next up |
| 1 | Lying set: breathing + 8 lying fidgets | Tier 1/2 |
| 2 | Gaits: all 6 walk cycles | Tier 1/2 |
| 3 | Standing set: alert-stand + 9 standing fidgets | Tier 2 |
| 4 | One-shots: 7 (+ bounce/greet-wag loops) | Tier 2/3 |
| 5 | Props | direct draw |
| 6 | Pack, renderer swap, verify_phase6, on-screen test | integration |

Per batch: I produce → you watch the preview GIFs → approve or flag → flagged items get
redone (or routed to your generator tool) before anything is integrated. Nothing lands in the
app unapproved.

## Your total workload

Watch GIFs and say yes/no per batch; optionally regenerate a handful of Tier 3 clips with
prompts I hand you. No drawing, no coding.

## Acceptance criteria (Phase 6 done)

- 34 animations + 5 props present at inventory frame counts, single master palette.
- Baseline-aligned: no foot-slide or vertical pop between state transitions.
- App runs on sprites with procedural renderer fully removed, mirroring via pixmap flip.
- `tools/verify_phase6.py` passes; screenshots land in `verify/phase6/`.
