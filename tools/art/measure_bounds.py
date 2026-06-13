"""Measure content bounding boxes of every clip vs window/mask limits.

Dev diagnostic: frames are 128x128 with feet baseline y=116. The app window is
WIN_H px tall (dog drawn against its bottom edge) and the click mask allows
75px above ground at +/-52px around the dog center. Anything outside those
boxes is invisible / unclickable, so flag it here before tuning by eye.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
A = os.path.join(ROOT, "assets")

m = json.load(open(os.path.join(A, "manifest.json")))
print(f"{'clip':<14} {'minX':>4} {'maxX':>4} {'minY':>4} {'maxY':>4}  above_base  half_w")
worst_top, worst_w = 0, 0
for name, c in m["clips"].items():
    x0 = y0 = 999
    x1 = y1 = -1
    for fn in c["frames"]:
        a = np.asarray(Image.open(os.path.join(A, c["dir"], fn)).convert("RGBA"))
        ys, xs = np.nonzero(a[:, :, 3])
        if len(xs) == 0:
            continue
        x0 = min(x0, xs.min()); x1 = max(x1, xs.max())
        y0 = min(y0, ys.min()); y1 = max(y1, ys.max())
    above = 116 - y0
    halfw = max(64 - x0, x1 - 64)
    worst_top = max(worst_top, above); worst_w = max(worst_w, halfw)
    flag = " <-- taller than mask 75" if above > 75 else ""
    flag += " <-- wider than mask 52" if halfw > 52 else ""
    print(f"{name:<14} {x0:>4} {x1:>4} {y0:>4} {y1:>4}  {above:>6}     {halfw:>4}{flag}")
print(f"\nworst content height above baseline: {worst_top}px "
      f"(window holds 95, standing mask holds 75)")
print(f"worst half-width from frame center: {worst_w}px (standing mask half-width 52)")
for p in ["prop-bed.png", "prop-bowl-full.png", "prop-bowl-empty.png",
          "prop-ball.png", "prop-bone.png", "prop-zzz.png"]:
    im = Image.open(os.path.join(A, p))
    print(p, im.size)
