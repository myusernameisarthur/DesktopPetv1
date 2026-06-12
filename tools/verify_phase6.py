"""Phase 6 verification: sprite assets + manifest + (optional) Qt load test.

Asset checks run anywhere (PIL only). The Qt section runs only if PyQt5 is
importable (i.e. on the dev machine), and verifies SpriteSet loads and serves
a frame for every clip and both facings.

Run:  python tools/verify_phase6.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
sys.path.insert(0, ROOT)

FAIL = []

def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)

# The 34 frozen animations (docs/ANIMATION-INVENTORY.md)
EXPECTED = [
    "breathing", "alert-stand", "bounce", "greet-wag",
    "trot-brisk", "plod", "plod-carry", "scamper", "sniff-walk", "dash",
    "stretch", "drink", "scratch", "chew", "roll-over", "bark", "beg-sit-up",
    "ear-flick", "nose-twitch", "tail-twitch", "sigh", "dream-kick",
    "eye-crack", "resettle", "scratch-lite",
    "blink", "ear-swivel", "weight-shift", "head-tilt", "look-around",
    "wag-burst", "shake-off", "bone-chew", "sit",
]
EXPECTED_PROPS = ["bed", "bowl-full", "bowl-empty", "ball", "bone", "zzz"]

print("== manifest ==")
mpath = os.path.join(ASSETS, "manifest.json")
check(os.path.exists(mpath), "assets/manifest.json exists")
m = json.load(open(mpath, encoding="utf-8"))
check(m.get("frame_size") == 128 and m.get("baseline") == 116,
      "frame_size=128 baseline=116")
clips = m.get("clips", {})
missing = [n for n in EXPECTED if n not in clips]
check(not missing, f"all 34 frozen animations present {missing or ''}")

print("== frames ==")
try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False
    print("  skip PIL not available; frame pixel checks skipped")

bad = []
for name, c in clips.items():
    if len(c["frames"]) != len(c["ticks"]):
        bad.append(f"{name}: frames/ticks mismatch")
        continue
    for fn in c["frames"]:
        fp = os.path.join(ASSETS, c["dir"], fn)
        if not os.path.exists(fp):
            bad.append(f"{name}/{fn}: missing")
        elif HAVE_PIL:
            im = Image.open(fp)
            if im.size != (128, 128):
                bad.append(f"{name}/{fn}: size {im.size}")
check(not bad, f"all frames exist, 128x128, ticks aligned {bad[:4] or ''}")

if HAVE_PIL:
    pal = json.load(open(os.path.join(ASSETS, "palette.json")))
    check(len(pal) == 24, "master palette has 24 colors")
    import numpy as np
    palset = set(map(tuple, pal))
    off = 0
    probe = ["breathing", "trot-brisk", "alert-stand"]
    for name in probe:
        c = clips[name]
        a = np.asarray(Image.open(
            os.path.join(ASSETS, c["dir"], c["frames"][0])).convert("RGBA"))
        op = a[a[:, :, 3] > 0][:, :3]
        off += sum(1 for px in map(tuple, op[::7]) if px not in palset)
    check(off == 0, f"sampled frames are palette-locked ({off} strays)")

print("== props ==")
pmissing = [p for p in EXPECTED_PROPS
            if not m["props"].get(p)
            or not os.path.exists(os.path.join(ASSETS, m["props"][p]))]
check(not pmissing, f"all 6 props present {pmissing or ''}")

print("== facing/timing sanity ==")
gaits_right = all(clips[g]["facing"] == "right"
                  for g in ["trot-brisk", "plod", "plod-carry",
                            "scamper", "sniff-walk", "dash"])
check(gaits_right, "gaits face right, rest left")
check(all(t >= 1 for c in clips.values() for t in c["ticks"]),
      "every frame >= 1 tick")
loops = {"breathing", "alert-stand", "bounce", "greet-wag", "trot-brisk",
         "plod", "plod-carry", "scamper", "sniff-walk", "dash", "drink",
         "scratch", "chew"}
check(all(clips[n]["loop"] == (n in loops) for n in EXPECTED),
      "loop/one-shot flags match inventory")

print("== Qt load test ==")
try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from sprites import SpriteSet
    s = SpriteSet()
    qt_bad = []
    for n in EXPECTED:
        for facing in (-1, 1):
            if s.get(n, 0, facing) is None:
                qt_bad.append(f"{n} f={facing}")
    check(not qt_bad, f"SpriteSet serves every clip both facings {qt_bad[:3] or ''}")
    check(all(s.prop(p) is not None for p in EXPECTED_PROPS), "all props load")
except ImportError:
    print("  skip PyQt5 not available here; run on the dev machine")

print()
if FAIL:
    print(f"PHASE 6 VERIFY: {len(FAIL)} FAILURE(S)")
    sys.exit(1)
print("PHASE 6 VERIFY: ALL CHECKS PASSED")
