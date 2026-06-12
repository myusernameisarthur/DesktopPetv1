"""Shared art-pipeline functions for Phase 6 (Batch 0+).

Conventions:
- Native frame canvas: 128x128 RGBA, feet baseline at y=BASELINE.
- Master palette: assets/palette.json (list of [r,g,b]); every frame is quantized to it.
- Cleaned frames: assets/frames/<clip>/<NN>.png in animation order.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "references"
ASSETS = ROOT / "assets"
FRAMES = ASSETS / "frames"
PREVIEWS = ROOT / "OUTPUTS" / "persi-art" / "previews"

CANVAS = 128
BASELINE = 116          # feet line, leaves room for shadow later
GRID_BG = (71, 112, 76) # flat green of the AI sheets
KEY_TOL = 45


# ---------------------------------------------------------------- slicing

def slice_grid(path: Path, rows: int = 5, cols: int = 5) -> list[Image.Image]:
    im = Image.open(path).convert("RGBA")
    tw, th = im.width // cols, im.height // rows
    return [im.crop((c * tw, r * th, (c + 1) * tw, (r + 1) * th))
            for r in range(rows) for c in range(cols)]


def slice_strip(path: Path, bg_tol: int = 60, min_gap: int = 6) -> list[Image.Image]:
    """Slice a horizontal strip on a flat background by column gaps."""
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im).astype(int)
    bg = a[0, 0, :3]
    mask = np.abs(a[:, :, :3] - bg).sum(axis=2) > bg_tol
    col = mask.any(axis=0)
    frames, x = [], 0
    while x < len(col):
        if col[x]:
            x0 = x
            gap = 0
            while x < len(col) and gap < min_gap:
                gap = gap + 1 if not col[x] else 0
                x += 1
            frames.append(im.crop((max(0, x0 - 2), 0, min(im.width, x - gap + 2), im.height)))
        else:
            x += 1
    return frames


def key_out(tile: Image.Image, bg=GRID_BG, tol: int = KEY_TOL) -> Image.Image:
    a = np.asarray(tile.convert("RGBA")).astype(int)
    d = np.abs(a[:, :, :3] - np.array(bg)).sum(axis=2)
    a[:, :, 3] = np.where(d < tol, 0, a[:, :, 3])
    return Image.fromarray(a.astype(np.uint8))


def key_out_auto(tile: Image.Image, tol: int = 60) -> Image.Image:
    """Key using the tile's own corner color (for non-green sources)."""
    a = np.asarray(tile.convert("RGBA")).astype(int)
    return key_out(tile, bg=tuple(a[0, 0, :3]), tol=tol)


def despeckle(img: Image.Image, min_px: int = 6) -> Image.Image:
    """Drop tiny opaque islands (4-connected flood fill, numpy only)."""
    a = np.array(img)
    alpha = a[:, :, 3] > 0
    seen = np.zeros_like(alpha, dtype=bool)
    h, w = alpha.shape
    for y in range(h):
        for x in range(w):
            if alpha[y, x] and not seen[y, x]:
                stack, comp = [(y, x)], []
                seen[y, x] = True
                while stack:
                    cy, cx = stack.pop()
                    comp.append((cy, cx))
                    for ny, nx in ((cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)):
                        if 0 <= ny < h and 0 <= nx < w and alpha[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
                if len(comp) < min_px:
                    for cy, cx in comp:
                        a[cy, cx, 3] = 0
    return Image.fromarray(a)


def dedupe(frames: list[Image.Image], thresh: float = 1.0) -> list[Image.Image]:
    """Keep frames in order, dropping near-exact duplicates of any kept frame."""
    kept, arrs = [], []
    for f in frames:
        a = np.asarray(f)[:, :, :3].astype(int)
        if all(np.abs(a - k).mean() >= thresh for k in arrs):
            kept.append(f)
            arrs.append(a)
    return kept


# ---------------------------------------------------------------- palette

def extract_palette(frames: list[Image.Image], n: int = 24) -> np.ndarray:
    """Median-cut palette from opaque pixels of all frames."""
    pix = []
    for f in frames:
        a = np.asarray(f)
        pix.append(a[a[:, :, 3] > 0][:, :3])
    allpix = np.concatenate(pix)
    flat = Image.fromarray(allpix.reshape(1, -1, 3))
    q = flat.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = np.array(q.getpalette()[: n * 3]).reshape(-1, 3)
    return pal


def resize_premult(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """LANCZOS resize without dark edge fringe: premultiply alpha first."""
    a = np.asarray(img).astype(np.float64)
    alpha = a[:, :, 3:4] / 255.0
    pm = np.concatenate([a[:, :, :3] * alpha, a[:, :, 3:4]], axis=2)
    pm_img = Image.fromarray(pm.astype(np.uint8)).resize(size, Image.LANCZOS)
    b = np.asarray(pm_img).astype(np.float64)
    out_alpha = b[:, :, 3:4]
    safe = np.maximum(out_alpha / 255.0, 1e-6)
    rgb = np.clip(b[:, :, :3] / safe, 0, 255)
    return Image.fromarray(
        np.concatenate([rgb, out_alpha], axis=2).astype(np.uint8))


def quantize_to(img: Image.Image, palette: np.ndarray,
                alpha_thresh: int = 128) -> Image.Image:
    a = np.array(img)
    opaque = a[:, :, 3] >= alpha_thresh
    rgb = a[:, :, :3].astype(int)
    d = ((rgb[:, :, None, :] - palette[None, None, :, :]) ** 2).sum(axis=3)
    nearest = palette[d.argmin(axis=2)]
    a[:, :, :3] = np.where(opaque[:, :, None], nearest, a[:, :, :3])
    a[:, :, 3] = np.where(opaque, 255, 0)  # binary alpha = crisp pixel edges
    a[:, :, :3] = np.where(opaque[:, :, None], a[:, :, :3], 0)
    return Image.fromarray(a.astype(np.uint8))


def drift_report(frames: list[Image.Image], palette: np.ndarray) -> list[float]:
    """Mean RGB distance of each frame's opaque pixels to nearest palette color."""
    out = []
    for f in frames:
        a = np.asarray(f)
        rgb = a[a[:, :, 3] > 0][:, :3].astype(int)
        d = np.sqrt((((rgb[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)).min(axis=1))
        out.append(round(float(d.mean()), 2))
    return out


# ---------------------------------------------------------------- normalize

def clip_bbox(frames: list[Image.Image]) -> tuple[int, int, int, int]:
    x0 = y0 = 10**9
    x1 = y1 = -1
    for f in frames:
        a = np.asarray(f)[:, :, 3] > 0
        ys, xs = np.where(a)
        if len(xs):
            x0, y0 = min(x0, xs.min()), min(y0, ys.min())
            x1, y1 = max(x1, xs.max()), max(y1, ys.max())
    return x0, y0, x1, y1


def normalize_clip(frames: list[Image.Image], scale: float,
                   canvas: int = CANVAS, baseline: int = BASELINE) -> list[Image.Image]:
    """Single crop+scale+offset for the whole clip (preserves relative motion).

    Feet line = 95th percentile of per-frame content bottoms, sits at `baseline`.
    """
    x0, y0, x1, y1 = clip_bbox(frames)
    cropped = [f.crop((x0, y0, x1 + 1, y1 + 1)) for f in frames]
    if scale != 1.0:
        size = (max(1, round(cropped[0].width * scale)),
                max(1, round(cropped[0].height * scale)))
        cropped = [resize_premult(c, size) for c in cropped]
    bottoms = []
    for c in cropped:
        a = np.asarray(c)[:, :, 3] > 0
        ys, _ = np.where(a)
        bottoms.append(ys.max() if len(ys) else 0)
    feet = int(np.percentile(bottoms, 95))
    ox = (canvas - cropped[0].width) // 2
    oy = baseline - feet
    out = []
    for c in cropped:
        cv = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        cv.alpha_composite(c, (ox, oy))
        out.append(cv)
    return out


# ---------------------------------------------------------------- output

def save_clip(name: str, frames: list[Image.Image]) -> Path:
    d = FRAMES / name
    d.mkdir(parents=True, exist_ok=True)
    stale = [p for p in d.glob("*.png") if int(p.stem) >= len(frames)]
    if stale:
        print(f"  WARNING {name}: {len(stale)} stale frames beyond index "
              f"{len(frames)-1} — delete manually: {[p.name for p in stale]}")
    for i, f in enumerate(frames):
        f.save(d / f"{i:02d}.png")
    return d


def load_clip(name: str) -> list[Image.Image]:
    d = FRAMES / name
    return [Image.open(p).convert("RGBA") for p in sorted(d.glob("*.png"))]


def preview_gif(name: str, frames: list[Image.Image], ms_per_frame: int = 95,
                scale: int = 2, bg=(225, 225, 225)) -> Path:
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    out = []
    for f in frames:
        c = Image.new("RGBA", f.size, bg + (255,))
        c.alpha_composite(f)
        c = c.resize((f.width * scale, f.height * scale), Image.NEAREST)
        out.append(c.convert("P", palette=Image.Palette.ADAPTIVE))
    p = PREVIEWS / f"{name}.gif"
    out[0].save(p, save_all=True, append_images=out[1:], duration=ms_per_frame, loop=0)
    return p


def palette_swatch(palette: np.ndarray, cell: int = 32) -> Image.Image:
    n = len(palette)
    im = Image.new("RGB", (cell * n, cell))
    for i, (r, g, b) in enumerate(palette):
        im.paste((int(r), int(g), int(b)), (i * cell, 0, (i + 1) * cell, cell))
    return im


def save_palette(palette: np.ndarray) -> None:
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "palette.json").write_text(json.dumps(palette.tolist()))
    palette_swatch(palette).save(ASSETS / "palette.png")


def load_palette() -> np.ndarray:
    return np.array(json.loads((ASSETS / "palette.json").read_text()))

# end of artlib
