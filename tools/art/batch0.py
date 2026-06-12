"""Batch 0: slice sources, master palette, cleaned+normalized master clips, previews.

Outputs:
  assets/palette.json + palette.png
  assets/frames/{walk-raw,sleep-raw,strip-raw}/NN.png  (128x128, quantized, baseline-aligned)
  OUTPUTS/persi-art/previews/{walk-raw,sleep-raw,strip-raw}.gif + palette.png
"""
import numpy as np
from PIL import Image

import artlib as A

# 1. slice + key + despeckle ------------------------------------------------
walk = [A.despeckle(A.key_out(t)) for t in A.slice_grid(A.REF / "Persi-walk.png")]
sleep = [A.despeckle(A.key_out(t)) for t in A.slice_grid(A.REF / "Persi2-sleep.png")]
strip = [A.despeckle(A.key_out_auto(f)) for f in A.slice_strip(A.REF / "dog sprite.png")]

walk = A.dedupe(walk)
sleep = A.dedupe(sleep)
print(f"unique frames -> walk {len(walk)}, sleep {len(sleep)}, strip {len(strip)}")

# 2. master palette from ALL sources ----------------------------------------
palette = A.extract_palette(walk + sleep + strip, n=24)
A.save_palette(palette)
print(f"palette: {len(palette)} colors")
print("drift before quantize (walk):", A.drift_report(walk[:5], palette))

# 3. normalize: scale so grid sources land at dog ~100px wide on 128 canvas --
# grid dog content is ~200px wide at 256 -> scale 0.5
# strip: match standing height to walk standing height after scaling
walk_n = A.normalize_clip(walk, scale=0.5)
sleep_n = A.normalize_clip(sleep, scale=0.5)

wx0, wy0, wx1, wy1 = A.clip_bbox(walk)
walk_h = (wy1 - wy0 + 1) * 0.5
sx0, sy0, sx1, sy1 = A.clip_bbox(strip[1:])  # standing frames only
strip_scale = walk_h / (sy1 - sy0 + 1)
strip_n = A.normalize_clip(strip, scale=strip_scale)
print(f"strip scale {strip_scale:.3f}")

# 4. quantize + save + preview ----------------------------------------------
for name, frames in [("walk-raw", walk_n), ("sleep-raw", sleep_n), ("strip-raw", strip_n)]:
    q = [A.quantize_to(f, palette) for f in frames]
    A.save_clip(name, q)
    A.preview_gif(name, q, ms_per_frame=95 if name != "sleep-raw" else 140)
    print(f"{name}: {len(q)} frames saved + preview")

A.palette_swatch(palette).save(A.PREVIEWS / "palette.png")
print("done")
