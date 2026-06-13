# Persi — Development Next Steps

Updated: 2026-06-12, end of Phase 6 **integration** session (see docs/PHASE-6-REPORT.md).
Ordered; each step has a done-condition.

## ~~Step 0 — First run on your machine~~ DONE 2026-06-12
verify_phase6 passes on the dev machine including the Qt load test (Pillow +
numpy installed so the pixel checks run too). App runs clean from source.

## ~~Step 1 — Integration fixes~~ DONE 2026-06-12 (integration session)
- **Mask was clipping every sprite** (content up to ±61px wide vs ±52px mask;
  lying content 46px tall vs 38px mask) — mask now sized to sprite extents.
- **sniff-walk pause** now holds/alternates the 2 sniff frames (frames 8–9)
  and the stride loops frames 0–7 (SpriteSet.get_range).
- **One-shot durations** (roll-over, bark, beg) now read the active clip's
  length, so behavior and animation end together.
- **Scale bump** solved properly: right-click → Art → Size (75%–200%),
  nearest-neighbor crisp, persisted as `art.scale`.
- **Sprite kit selector**: Art menu radio — "Classic shapes (procedural)" vs
  "Pixel-art sprites" (`art.kit`; old `art.sprites` bool migrates). Drop-in
  future kits: a folder `assets/kits/<name>/` with its own manifest.json.
- **Startup climb** (owner-requested, post-freeze addition): dog hauls up from
  behind the taskbar on launch, then greets. Procedural placeholder —
  `climb-up` clip is an open art item (OPEN-ITEMS.md); the renderer picks it
  up automatically once a clip with that name lands in the manifest.
- **tools/art/pack.py was missing from the repo** (the build session only
  committed its output). Reconstructed; regenerates manifest.json
  byte-identically. The timing table is in TICKS (33 ms each), not ms.
- New smoke harness `python tools/smoke_phase6.py` renders real states to
  verify/phase6/*.png and asserts the integration logic — run it after
  renderer/timing changes.
- Mirrored-facing check (does flipping Persi's markings bother you in
  motion?): **still yours to judge at desk distance.**

## Step 2 — Timing tuning (cheap, high value)
Frame durations live in tools/art/pack.py (ticks table, 33 ms per tick) →
rerun to regenerate manifest.json. No code changes needed. Tune while
watching the live app.
Done when: idle Persi feels alive at desk distance for a full workday.

## Step 3 — Regenerate the 19 flagged clips (external tool + pipeline)
Per OPEN-ITEMS.md spec tables (standing set ×10, batch-4 set ×9):
1. In your generator tool, use the standing/lying reference frame as character
   ref, generate each clip as a 5×5 grid, 256px tiles, flat green background.
2. Drop sheets into references/, run the pipeline (slice → key → despeckle →
   palette-lock → normalize), save over the clip in assets/frames/<name>/.
   NOTE: if a new clip has FEWER frames than the old one, delete the stale
   higher-numbered PNGs manually (the pipeline can't delete files).
3. Review loop: preview GIF per clip in OUTPUTS/persi-art/previews/ before it
   lands.
4. Update pack.py ticks if frame counts changed; rerun pack + verify_phase6
   + smoke_phase6.
Done when: OPEN-ITEMS.md has no open art items. This is the ship-blocking art
gate.

## Step 3b — climb-up clip (new, smallest art item)
One ~10-frame one-shot, facing left, standing ref: paws hook over a ledge at
the baseline, haul up, settle shake (full spec in OPEN-ITEMS.md). Lands like
any other clip: frames in assets/frames/climb-up/, add a pack.py row, rerun.
No code needed — biscuit.py already plays a clip named `climb-up` for the
CLIMBING state when present.

## Step 4 — Prop polish (small)
Bed reads as a flat brown puddle (and is fully hidden behind the 128px-wide
dog frames when she sleeps); bowl/ball/bone are passable. Redraw bed (and any
prop you dislike) at native size, or generate via the same external tool.
Done when: corner scene looks intentional.

## Step 5 — Phase 4 deferred hooks (optional, see PHASE-4-HOOKS-DESIGN.md)
type-along (`typewrite` animation + typewriter prop, 3–4 frames) and
window-bark (reuses `bark`, already real art). Adds ONE new animation + one
prop to the inventory. Ship type-along default-off per the roadmap decision.
Done when: both hooks work behind settings toggles.

## Step 6 — Phase 7 polish (per roadmap)
- multi-monitor + DPI: sprite path needs devicePixelRatio handling for
  crispness on scaled displays (QPixmap.setDevicePixelRatio at load)
- perf pass: pixmaps are cached, mirrors lazy — profile paint time anyway
  (the size toggle adds a painter transform; profile at 200% too)
- HUD default off (settings.py DEFAULTS flip)
- the procedural renderer is now a first-class "kit" choice (Art menu), not a
  fallback toggle — keeping it permanently is the working decision; revisit
  only if it blocks a refactor
- settings UI decision (menu vs small window) — open roadmap question #5

## Step 7 — Phase 8 ship
- rebuild exe (`pyinstaller Biscuit.spec` — assets bundled), test on a clean
  machine/profile
- code-sign, installer, startup default, update mechanism (roadmap)

## Standing conventions (don't break these)
- Frames: 128×128 PNG, baseline y=116, 24-color palette (assets/palette.json),
  binary alpha. Gaits face right, everything else faces left.
- manifest.json is generated by tools/art/pack.py — never hand-edit it.
  Timing lives in pack.py's CLIPS table (per-frame ticks of 33 ms).
- After every change: `python tools/verify_phase6.py` must pass; run
  `python tools/smoke_phase6.py` after renderer/timing changes.
- Every art change goes through a preview GIF in OUTPUTS/persi-art/previews/
  and gets explicit approval before integration.
- Loop seams must be invisible; motion deltas even; only flesh bends (taper),
  rigid sections never slide.
