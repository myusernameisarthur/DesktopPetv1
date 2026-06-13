"""Sprite renderer for Persi (Phase 6).

Loads a kit's manifest.json + per-frame PNGs produced by tools/art/, and draws
the right frame for the current state/fidget. Designed to coexist with the
procedural renderer: every lookup degrades to None so biscuit.py can fall back
per-state while art is iterated. The active kit is chosen via settings key
"art.kit" ("procedural" = no sprites; see available_kits()).

Anchoring: frames are 128x128 with the feet baseline at y=116. The window's
dog baseline is `base` (DOG_BASE - bounce), so frames are blitted at
(cx - 64, base - 116). Facing is normalized by mirroring: each clip declares
its native facing in the manifest; app facing is -1=left, 1=right.
"""

import json
import os

from PyQt5.QtGui import QPixmap, QTransform

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Fidget engine names that differ from clip names
FIDGET_CLIP = {"scratch": "scratch-lite"}


def available_kits():
    """Sprite kits on disk, as {kit_name: assets_dir}.

    The Phase 6 pixel-art kit lives at assets/ root under the name "pixel".
    Additional kits are drop-in directories assets/kits/<name>/ holding their
    own manifest.json + frames + props, packed by their own tools/art run.
    The procedural renderer is not a kit — biscuit.py offers it as the
    "procedural" choice that simply loads no SpriteSet.
    """
    kits = {}
    if os.path.exists(os.path.join(ASSETS_DIR, "manifest.json")):
        kits["pixel"] = ASSETS_DIR
    kits_dir = os.path.join(ASSETS_DIR, "kits")
    if os.path.isdir(kits_dir):
        for name in sorted(os.listdir(kits_dir)):
            d = os.path.join(kits_dir, name)
            if os.path.exists(os.path.join(d, "manifest.json")):
                kits[name] = d
    return kits


class _Clip:
    __slots__ = ("frames", "mirrored", "ticks", "starts", "total", "loop", "facing")

    def __init__(self, frames, ticks, loop, facing):
        self.frames = frames                  # list[QPixmap]
        self.mirrored = [None] * len(frames)  # lazy
        self.ticks = ticks                    # per-frame duration in ticks
        self.starts = []                      # cumulative start tick per frame
        t = 0
        for d in ticks:
            self.starts.append(t)
            t += d
        self.total = t
        self.loop = loop
        self.facing = 1 if facing == "right" else -1

    def index_at(self, tick):
        t = tick % self.total if self.loop else min(tick, self.total - 1)
        # frames are few (<=12): linear scan is fine
        for i in range(len(self.starts) - 1, -1, -1):
            if t >= self.starts[i]:
                return i
        return 0

    def index_in_range(self, tick, first, last):
        """Frame index looping over the sub-range [first, last] only (used by
        sniff-walk: stride frames while walking, the 2 sniff frames on pause)."""
        span = self.starts[last] + self.ticks[last] - self.starts[first]
        t = self.starts[first] + tick % span
        for i in range(last, first - 1, -1):
            if t >= self.starts[i]:
                return i
        return first

    def at(self, i, facing):
        if facing == self.facing:
            return self.frames[i]
        if self.mirrored[i] is None:
            self.mirrored[i] = self.frames[i].transformed(QTransform().scale(-1, 1))
        return self.mirrored[i]

    def pixmap(self, tick, facing):
        return self.at(self.index_at(tick), facing)


class SpriteSet:
    """All clips + props from one kit's manifest. Raises on missing manifest;
    individual missing clips just return None from get()."""

    def __init__(self, assets_dir=ASSETS_DIR):
        with open(os.path.join(assets_dir, "manifest.json"), encoding="utf-8") as fh:
            m = json.load(fh)
        self.frame_size = m["frame_size"]
        self.baseline = m["baseline"]
        self.clips = {}
        for name, c in m["clips"].items():
            pms = []
            for fn in c["frames"]:
                p = QPixmap(os.path.join(assets_dir, c["dir"], fn))
                if p.isNull():
                    pms = []
                    break
                pms.append(p)
            if pms:
                self.clips[name] = _Clip(pms, c["ticks"], c["loop"], c["facing"])
        self.props = {}
        for name, fn in m.get("props", {}).items():
            if fn:
                p = QPixmap(os.path.join(assets_dir, fn))
                if not p.isNull():
                    self.props[name] = p

    def has(self, name):
        return name in self.clips

    def get(self, name, tick, facing):
        """QPixmap for clip `name` at `tick` (ticks since clip start for
        one-shots, any monotonic counter for loops), or None."""
        c = self.clips.get(name)
        return c.pixmap(tick, facing) if c else None

    def get_range(self, name, tick, facing, first, last):
        """QPixmap looping over frames [first, last] of clip `name`, or None."""
        c = self.clips.get(name)
        if not c or not (0 <= first <= last < len(c.frames)):
            return None
        return c.at(c.index_in_range(tick, first, last), facing)

    def fidget_pixmap(self, fidget_name, progress, facing):
        """Frame for an active fidget, indexed by engine progress (0..1) so
        clip length and engine duration never drift apart."""
        c = self.clips.get(FIDGET_CLIP.get(fidget_name, fidget_name))
        if not c:
            return None
        i = min(len(c.frames) - 1, int(progress * len(c.frames)))
        return c.at(i, facing)

    def draw_dog(self, p, pixmap, cx, base):
        p.drawPixmap(cx - self.frame_size // 2, base - self.baseline, pixmap)

    def prop(self, name):
        return self.props.get(name)
