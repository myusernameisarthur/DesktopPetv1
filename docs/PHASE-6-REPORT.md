# Phase 6 Report — Real art in-app: sprite renderer integrated, tuned, and extended

Date: 2026-06-12 · Branch: `feature/phase-6-art` · Tag on merge: `phase-6-complete`

Phase 6 happened in two sessions: a **build session** (Cowork) that produced the art
pipeline, 34 sprite clips + 6 props, and the manifest-driven renderer (commit b338ef5),
and this **integration session** that made it correct on a real machine and added the
owner-requested controls. The art itself is split into approved sets and 19+1 clips
awaiting regeneration — see OUTPUTS/persi-art/OPEN-ITEMS.md, the ship-blocking art gate.

## What the integration session fixed

- **The mask was clipping every sprite.** The click/paint mask predates the sprites
  (procedural dog ≈ 104 px wide). Measured sprite content (tools/art/measure_bounds.py)
  runs to ±61 px from frame center and 70 px above the baseline, so noses, tails and the
  top of the lying pose were cut off. The mask is now sized to the sprite extents whenever
  a kit is active (one rect for all poses) and scales with the size toggle.
- **sniff-walk pause** looped the whole 10-frame clip. It now plays as two sub-loops of
  one clip: stride frames 0–7 while travelling, the two nose-down sniff frames 8–9 during
  a pause (`SpriteSet.get_range`, driven by `task_phase`).
- **One-shot behavior durations** (roll-over 75→85 ticks, bark 26→24, beg 50→52) now read
  the active kit's clip length (`_one_shot_ticks`), so the state machine and the animation
  end together; procedural defaults still apply when no clip exists.
- **tools/art/pack.py was missing** — the build session committed only its output.
  Reconstructed from the manifest; regenerating is byte-identical. Timing table is
  per-frame TICKS (33 ms each).

## What the integration session added (owner requests)

- **Sprite-kit selector** (right-click → Art): "Classic shapes (procedural)" vs
  "Pixel-art sprites", persisted as `art.kit` (the Phase 6 `art.sprites` bool migrates).
  Future kits are drop-in folders `assets/kits/<name>/` with their own manifest —
  discovered automatically, zero code.
- **Size toggle** (right-click → Art): 75% / 100% / 125% / 150% / 200%, persisted as
  `art.scale`. Implemented as a QPainter transform anchored at the feet-ground point —
  nearest-neighbor, so pixel art stays crisp; props, mask, hit-tests, bubble anchors and
  corner layout spacing all scale with it. WIN_H grew 95→190 to fit the 200% dog
  (everything is bottom-anchored, so the extra height is invisible masked area).
- **Startup climb** (`State.CLIMBING`, switch `reactive.startup_climb`, Test menu entry):
  on launch the dog hauls up from behind the taskbar like a ledge — paws hook over the
  edge, head peeks with effort-bobs, body scrambles up, settle shake — then the greet
  fires. Drawn procedurally as a **placeholder by design**: the pixel kit has no climb
  art yet. The renderer plays a sprite clip named `climb-up` automatically once one lands
  in the manifest (spec in OPEN-ITEMS.md; inventory exception noted like type-along).
  This is a deliberate post-freeze behavior addition, owner-approved 2026-06-12.

## Verification

- `python tools/verify_phase6.py` — ALL PASS on the dev machine, including the Qt load
  test (first real-machine run) and the PIL pixel checks (Pillow + numpy installed).
- `python tools/smoke_phase6.py` (new) — instantiates the real widget against a throwaway
  APPDATA, asserts: settings migration, kit switching, one-shot duration sync, sniff
  sub-loop indices; renders 15 real-state grabs to `verify/phase6/` (sleeping, alert,
  trot, sniff stride/pause, beg, corner, climb 20/60/95%, 2× scale, procedural kit) —
  all eyeballed correct.
- App ran from source for 9 s with the full launch sequence (climb → greet), zero stderr.

## HUD

New `ART` line shows `<kit> x<scale>` (e.g. `pixel x1.25`); CLIMBING reports `% done`;
the HUD floats higher when the dog is scaled up.

## Carry-forward (the art gate, unchanged)

19 clips are approved-as-placeholder pending regeneration (10 standing, 9 batch-4) plus
the new `climb-up` — spec tables in OPEN-ITEMS.md, workflow in NEXT-STEPS.md steps 3/3b.
Timing tuning at desk distance (step 2) remains a live session with Arthur.
