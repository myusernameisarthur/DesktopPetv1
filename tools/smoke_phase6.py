"""Phase 6 integration smoke test: render real states to PNGs + assert logic.

Instantiates the live Biscuit widget against a throwaway APPDATA (no event
loop, so nothing animates on screen and the user's settings are untouched),
forces states / kits / scales, and saves widget grabs to verify/phase6/ for
eyeball review. Also asserts the new Phase 6 integration logic: sniff-walk
sub-loops, one-shot durations synced to clip lengths, kit switching, and the
art.sprites -> art.kit settings migration.

Run:  python tools/smoke_phase6.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "verify", "phase6")
os.makedirs(OUT, exist_ok=True)

FAILS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


# ── settings migration (own APPDATA, before the app's) ──────────────────────
mig_dir = tempfile.mkdtemp(prefix="persi-mig-")
os.environ["APPDATA"] = mig_dir
import json

os.makedirs(os.path.join(mig_dir, "Persi"), exist_ok=True)
with open(os.path.join(mig_dir, "Persi", "settings.json"), "w") as fh:
    json.dump({"art.sprites": False}, fh)
import settings as settings_mod

s = settings_mod.Settings()
check(s.get("art.kit") == "procedural",
      "legacy art.sprites=false migrates to art.kit=procedural")
with open(os.path.join(mig_dir, "Persi", "settings.json")) as fh:
    on_disk = json.load(fh)
check(on_disk.get("art.kit") == "procedural",
      "migration is persisted to disk immediately (not just in memory)")
s2_dir = tempfile.mkdtemp(prefix="persi-fresh-")
os.environ["APPDATA"] = s2_dir
s2 = settings_mod.Settings()
check(s2.get("art.kit") == "pixel" and s2.get("art.scale") == 1.0
      and s2.get("reactive.startup_climb") is True,
      "fresh defaults: kit=pixel scale=1.0 climb=on")

# ── live widget ──────────────────────────────────────────────────────────────
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="persi-smoke-")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QRect

app = QApplication(sys.argv)
import biscuit
from biscuit import Biscuit, State, WIN_H

dog = Biscuit()
check(dog.sprites is not None, "pixel kit loaded at startup")
check(dog.state == State.CLIMBING, "starts in CLIMBING (startup climb on)")

# one-shot durations follow the active kit's clip lengths
check(dog._one_shot_ticks("roll-over", 75) == 85, "roll-over duration = clip 85")
check(dog._one_shot_ticks("bark", 26) == 24, "bark duration = clip 24")
check(dog._one_shot_ticks("beg-sit-up", 50) == 52, "beg duration = clip 52")
check(dog._one_shot_ticks("climb-up", 80) == 80, "climb-up has no clip -> default")

# sniff-walk sub-loops: stride frames 0..7 while walking, 8..9 in the pause
c = dog.sprites.clips["sniff-walk"]
walk_idx = {c.index_in_range(t, 0, 7) for t in range(0, 48)}
pause_idx = {c.index_in_range(t, 8, 9) for t in range(0, 32)}
check(walk_idx == set(range(8)), f"sniff stride loops frames 0-7 {sorted(walk_idx)}")
check(pause_idx == {8, 9}, f"sniff pause alternates frames 8-9 {sorted(pause_idx)}")


# climb flag: only the launch path arms the greet chain; _start_climb is inert
dog._climb_then_greet = True
dog._start_climb()
check(dog._climb_then_greet is False,
      "_start_climb() clears _climb_then_greet (no spurious test-climb greet)")

# zoomies dash bounds recompute when the scale changes mid-run, so the dog
# never dashes into the relocated corner
dog._start_zoomies()
dog.dog_sx = float(dog.zoom_left)
dog.zoom_dest = dog.zoom_right            # heading right toward the corner
old_right = dog.zoom_right
dog._set_art_scale(2.0)
check(dog.zoom_right < dog.bed_cx and dog.zoom_right != old_right,
      "zoomies right bound stays left of the rescaled bed")
dog._set_art_scale(1.0)
dog.state = State.SLEEPING

# invalid persisted art.kit heals on next construction (own widget + APPDATA)
bad_dir = tempfile.mkdtemp(prefix="persi-badkit-")
os.makedirs(os.path.join(bad_dir, "Persi"), exist_ok=True)
with open(os.path.join(bad_dir, "Persi", "settings.json"), "w") as fh:
    json.dump({"art.kit": "ghostkit"}, fh)
os.environ["APPDATA"] = bad_dir
dog2 = Biscuit()
check(dog2.art_kit in ("pixel", "procedural"), "invalid art.kit falls back in memory")
with open(os.path.join(bad_dir, "Persi", "settings.json")) as fh:
    check(json.load(fh).get("art.kit") == dog2.art_kit,
          "invalid art.kit healed on disk")
dog2._hud.close()
dog2.close()
os.environ["APPDATA"] = os.path.dirname(os.path.dirname(dog.settings.path))


def grab(name, x_center, half_w=150):
    pm = dog.grab(QRect(int(x_center - half_w), 0, half_w * 2, WIN_H))
    path = os.path.join(OUT, name + ".png")
    pm.save(path)
    print("  shot", os.path.relpath(path, ROOT))


def force(state, task_phase=0, task_frames=0, ticks=0, facing=-1):
    dog.state = state
    dog.task_phase = task_phase
    dog.task_frames = task_frames
    dog._ticks = ticks
    dog.facing = facing
    dog.bounce_val = 0.0
    dog.fidgets.cancel()


# pixel kit, normal size
force(State.SLEEPING)
grab("pixel-sleeping", dog.dog_sx)
force(State.ALERT)
grab("pixel-alert", dog.dog_sx)
force(State.WALKING, ticks=3, facing=1)
grab("pixel-trot", dog.dog_sx)
force(State.SNIFF_WALK, task_phase=0, ticks=4)
grab("pixel-sniff-stride", dog.dog_sx)
force(State.SNIFF_WALK, task_phase=1, ticks=2)
grab("pixel-sniff-pause", dog.dog_sx)
force(State.BEG, task_frames=30)
grab("pixel-beg", dog.dog_sx)
grab("pixel-corner", (dog.bed_cx + dog.tb_right) // 2, 130)

# climb placeholder phases (procedural by design — no climb-up clip yet)
sf = 80
dog.state_frames = sf
for pct in (20, 60, 95):
    force(State.CLIMBING, task_frames=int(sf * pct / 100))
    dog.state_frames = sf
    grab(f"climb-{pct}pct", dog.dog_sx)

# size toggle
dog._set_art_scale(2.0)
force(State.SLEEPING)
grab("pixel-sleeping-2x", dog.dog_sx, 200)
grab("pixel-corner-2x", (dog.bed_cx + dog.tb_right) // 2, 200)
force(State.ALERT)
grab("pixel-alert-2x", dog.dog_sx, 200)
dog._set_art_scale(1.0)

# kit switch: procedural (the old art), then back
dog._set_art_kit("procedural")
check(dog.sprites is None, "procedural kit -> no SpriteSet")
force(State.SLEEPING)
grab("procedural-sleeping", dog.dog_sx)
force(State.ALERT)
grab("procedural-alert", dog.dog_sx)
dog._set_art_kit("pixel")
check(dog.sprites is not None, "switch back to pixel kit")

dog._hud.close()
dog.close()

print()
if FAILS:
    print(f"SMOKE: {len(FAILS)} FAILURE(S)")
    sys.exit(1)
print("SMOKE: ALL CHECKS PASSED")
