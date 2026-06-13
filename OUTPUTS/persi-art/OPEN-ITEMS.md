# Phase 6 Art — Open Items

Updated: 2026-06-12 (integration session: added climb-up)

## OPEN: climb-up — new clip, no art exists yet (procedural placeholder in-app)

Owner-approved post-freeze addition (2026-06-12): on launch the dog climbs up
from behind the taskbar like a ledge, then greets. The app plays a procedural
placeholder today; biscuit.py automatically switches to a sprite clip named
`climb-up` the moment one lands in the manifest (add frames to
assets/frames/climb-up/, add a pack.py CLIPS row, rerun pack + verify).

### Regeneration spec (side view, facing left, standing ref)
| Clip | Frames | Prompt notes |
|------|--------|--------------|
| climb-up | ~10 | one-shot ~2.6s: front paws hook over a ledge at the baseline (2), head pulls up behind them with effort (3), body hauls up legs scrambling (3), settle + quick shake (2). The ledge is the frame baseline y=116 — author the climb IN the pose (paws-on-ledge), no below-baseline content needed. |

## OPEN: Standing set failed quality review — regenerate with external tool

Status: **kept as placeholders** in `assets/frames/` so behaviors can be wired up and
timing/feel tested in-app. Art to be replaced before ship.

Failed review (user, 2026-06-12): alert-stand, blink, ear-swivel, weight-shift, head-tilt,
look-around, wag-burst, shake-off, sit, bone-chew — all 10 standing clips. Root cause: the
standing pose has only ONE usable source frame (`dog sprite.png` frame 2; frames 3–4 are
different-dog AI generations, see audit). Synthesized pixel-shift motion on a single frame
was good enough for the lying set (approved) but not for standing, where the expected
motions (sit, chew, swivel) involve real pose/silhouette changes.

### Regeneration route
Generate each clip in the original sheet tool (PixelLab-style: 1280×1280, 5×5 grid,
256px tiles, flat green bg — pipeline auto-ingests this format) using the **standing pose
as character reference** (`assets/frames/strip-raw/01.png`, or original
`references/dog sprite.png` frame 2). Then run `tools/art/` pipeline: slice → key →
palette-lock → normalize → it lands consistent with the approved sets automatically.

### Per-clip regeneration spec (side view, facing left, standing)
| Clip | Frames | Prompt notes |
|------|--------|--------------|
| alert-stand | 4 | idle loop, ears up, gentle sway/breath, feet planted |
| blink | 2 | single blink, no other motion |
| ear-swivel | 3 | one ear rotates back then returns |
| weight-shift | 3 | weight rocks to back legs and returns |
| head-tilt | 4 | curious head tilt to one side, hold, return |
| look-around | 5 | head turns to look behind, hold, return |
| wag-burst | 4 | fast happy tail wag burst |
| shake-off | 6 | full-body wet-dog shake, ears flying |
| sit | 6 | sit down (2), hold (2), stand back up (2) |
| bone-chew | 8 | reach down to bone (2), gnaw (4), drop/stow (2) |

## OPEN: Batch 4 (bounce, greet-wag, 7 one-shots) — placeholder-grade by construction

These involve large pose changes (rearing up, rolling over, play-bow) that pixel-shifting
cannot do convincingly. Built 2026-06-12 as placeholders for behavior wiring;
**pre-flagged for the same external regeneration route.** Worst offenders: roll-over
(vertical flip stand-in), beg-sit-up and bark (transparent-gap mouths/joints).

### Per-clip regeneration spec
| Clip | Frames | Base pose | Prompt notes |
|------|--------|-----------|--------------|
| bounce | 6 | standing | excited hop loop, tongue out, fast tail wag |
| greet-wag | 6 | standing | happy greeting, small hops + big wag (~2.6s loop, can share cells with bounce) |
| stretch | 10 | standing | play-bow stretch: front down, rear up, yawn, settle (~4s) |
| drink | 6 | standing | head down lapping at bowl, head-bob loop |
| scratch | 8 | standing | hind leg scratching ear, body jitter, head tilted |
| chew | 6 | standing/lying | gnawing bone held in front paws, loop |
| bark | 5 | standing | head back, two bobs forward, mouth open/close (~1.2s) |
| beg-sit-up | 8 | sitting | sit up on haunches (3), hold + front paw paddle (3), down (2) |
| roll-over | 12 | lying | roll onto back (3), leg paddle (6), roll back upright (3) |

## Approved (final art)
- Lying set: breathing + 8 lying fidgets (sigh rebuilt symmetric)
- Gaits: trot-brisk, plod, plod-carry, sniff-walk, scamper, dash
- Props so far: ball (`assets/prop-ball.png`), bone (`assets/prop-bone.png`)

## Notes
- All clip facings are native (lying/standing face left, gaits face right); record per-clip
  facing in the Batch 6 manifest and normalize in the renderer.
- `sigh` is 6 frames (not the suggested 4) for symmetric rise/fall — approved.
