"""Persistent settings store for Biscuit/Persi.

One on/off switch per behavior, saved as JSON in %APPDATA%\\Persi\\settings.json
so toggles survive restarts. "Launch at startup" stays in the registry
(HKCU\\...\\Run) — Windows itself reads that key, so it can't move here.
"Pause animations" is deliberately session-only and not stored.

Unknown or wrong-typed keys in the file are ignored; missing keys fall back to
DEFAULTS, so adding a new behavior switch later needs only a new DEFAULTS row.
"""

import json
import os

DEFAULTS = {
    # Idle (ambient, self-triggered)
    "idle.fidgets_lying": True,
    "idle.fidgets_standing": True,
    "idle.wander_walk": True,
    "idle.scratch": True,
    "idle.chew": True,
    "idle.sniff_walk": True,
    "idle.zoomies": True,
    # Timed (clock)
    "timed.stretch_reminders": True,
    "timed.water_reminders": True,
    # Interactive (cursor / click)
    "interactive.cursor_alert": True,
    "interactive.excited_on_click": True,
    "interactive.fetch_ball": True,
    # Command (deliberate gesture)
    "command.roll_over": True,
    "command.beg": True,
    # Reactive (system events)
    "reactive.greet": True,
    "reactive.startup_climb": True,
    # Art (Phase 6): which sprite kit renders the dog ("procedural" = old
    # shape renderer; "pixel" = Phase 6 pixel art; see sprites.available_kits)
    # and the size multiplier applied to dog + props.
    "art.kit": "pixel",
    "art.scale": 1.0,
    # Debug (dev tooling; default flips off in Phase 7)
    "debug.hud": True,
}


class Settings:
    def __init__(self, app_name="Persi"):
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        self.dir = os.path.join(appdata, app_name)
        self.path = os.path.join(self.dir, "settings.json")
        self._data = dict(DEFAULTS)
        self._migrated = False
        self._load()
        if not os.path.exists(self.path) or self._migrated:
            # First run: materialize the defaults file. Migration: commit the
            # rewritten keys now so it doesn't re-run from the stale file on
            # every launch (it would, if the user never changes a setting).
            self.save()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                stored = json.load(fh)
        except FileNotFoundError:
            return
        except Exception as e:        # corrupt file: run on defaults, heal on next save
            print(f"Settings load error ({e}); using defaults")
            return
        for key, value in stored.items():
            if key in DEFAULTS and isinstance(value, type(DEFAULTS[key])):
                self._data[key] = value
        # Migration: "art.sprites" (Phase 6 bool) became "art.kit" (str).
        if "art.kit" not in stored and stored.get("art.sprites") is False:
            self._data["art.kit"] = "procedural"
            self._migrated = True

    def get(self, key):
        return self._data[key]

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def save(self):
        try:
            os.makedirs(self.dir, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except Exception as e:
            print(f"Settings save error: {e}")
