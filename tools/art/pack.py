"""Generate assets/manifest.json from the timing table below.

THE TIMING TABLE LIVES HERE. assets/manifest.json is generated output — never
hand-edit it. To retime a clip: edit its row, rerun `python tools/art/pack.py`,
then `python tools/verify_phase6.py`.

Durations are per-frame TICKS at the app's 33 ms tick (so 3 ticks ~ 100 ms,
30 ticks ~ 1 s). A single int applies to every frame of the clip; a list gives
each frame its own duration and must match the frame count on disk.

Frames are read from assets/frames/<clip>/ (sorted *.png), so a regenerated
clip with a different frame count only needs its ticks row updated here.
NOTE: the art pipeline never deletes files — if a new version of a clip has
FEWER frames, delete the stale higher-numbered PNGs by hand first.

History: the original Phase 6 build session lost this file (only its output,
manifest.json, was committed). Reconstructed 2026-06-12 from that manifest;
regenerating produces a byte-identical file.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(ROOT, "assets")

TICK_MS = 33
FRAME_SIZE = 128
BASELINE = 116

# clip: (per-frame ticks, loop, native facing)  — manifest order
CLIPS = {
    # base poses & idle loops
    "breathing":    ([21, 5, 17, 17, 5, 21],          True,  "left"),
    "alert-stand":  (13,                              True,  "left"),
    "bounce":       (2,                               True,  "left"),
    "greet-wag":    (13,                              True,  "left"),
    # gaits (face right)
    "trot-brisk":   (2,                               True,  "right"),
    "plod":         (5,                               True,  "right"),
    "plod-carry":   (5,                               True,  "right"),
    "scamper":      (2,                               True,  "right"),
    "sniff-walk":   ([3, 3, 3, 3, 3, 3, 3, 3, 8, 8],  True,  "right"),
    "dash":         (2,                               True,  "right"),
    # one-shots / task loops
    "stretch":      ([7, 7, 9, 13, 13, 9, 8, 7, 7, 8], False, "left"),
    "drink":        (4,                               True,  "left"),
    "scratch":      (2,                               True,  "left"),
    "chew":         (4,                               True,  "left"),
    "roll-over":    ([6, 8, 8, 7, 7, 7, 7, 7, 8, 8, 6, 6], False, "left"),
    "bark":         ([4, 4, 6, 5, 5],                 False, "left"),
    "beg-sit-up":   ([5, 5, 8, 8, 8, 8, 5, 5],        False, "left"),
    # lying fidgets
    "ear-flick":    (2,                               False, "left"),
    "nose-twitch":  (2,                               False, "left"),
    "tail-twitch":  ([2, 3, 2],                       False, "left"),
    "sigh":         ([7, 7, 15, 15, 7, 7],            False, "left"),
    "dream-kick":   (3,                               False, "left"),
    "eye-crack":    ([6, 15, 6],                      False, "left"),
    "resettle":     ([5, 5, 8, 6, 5, 5],              False, "left"),
    "scratch-lite": (2,                               False, "left"),
    # standing fidgets
    "blink":        (3,                               False, "left"),
    "ear-swivel":   ([3, 4, 3],                       False, "left"),
    "weight-shift": ([8, 8, 6],                       False, "left"),
    "head-tilt":    ([4, 13, 13, 4],                  False, "left"),
    "look-around":  ([4, 9, 9, 9, 4],                 False, "left"),
    "wag-burst":    (2,                               False, "left"),
    "shake-off":    (2,                               False, "left"),
    "sit":          ([5, 5, 21, 21, 5, 5],            False, "left"),
    "bone-chew":    ([5, 5, 4, 4, 4, 4, 5, 5],        False, "left"),
}

PROPS = {
    "ball": "prop-ball.png",
    "bone": "prop-bone.png",
    "bed": "prop-bed.png",
    "bowl-full": "prop-bowl-full.png",
    "bowl-empty": "prop-bowl-empty.png",
    "zzz": "prop-zzz.png",
}


def main():
    clips = {}
    errors = []
    for name, (ticks, loop, facing) in CLIPS.items():
        d = os.path.join(ASSETS, "frames", name)
        if not os.path.isdir(d):
            errors.append(f"{name}: missing dir {d}")
            continue
        frames = sorted(f for f in os.listdir(d) if f.endswith(".png"))
        if isinstance(ticks, int):
            ticks = [ticks] * len(frames)
        if len(ticks) != len(frames):
            errors.append(f"{name}: {len(frames)} frames on disk but "
                          f"{len(ticks)} tick entries in the table")
            continue
        clips[name] = {
            "dir": f"frames/{name}",
            "frames": frames,
            "ticks": ticks,
            "loop": loop,
            "facing": facing,
        }
    for prop, fn in PROPS.items():
        if not os.path.exists(os.path.join(ASSETS, fn)):
            errors.append(f"prop {prop}: missing {fn}")
    if errors:
        for e in errors:
            print("FAIL", e)
        sys.exit(1)

    manifest = {
        "frame_size": FRAME_SIZE,
        "baseline": BASELINE,
        "tick_ms": TICK_MS,
        "clips": clips,
        "props": PROPS,
    }
    out = os.path.join(ASSETS, "manifest.json")
    with open(out, "w", encoding="utf-8", newline="") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"wrote {out}: {len(clips)} clips, {len(PROPS)} props")


if __name__ == "__main__":
    main()
