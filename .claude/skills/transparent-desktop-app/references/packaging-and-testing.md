# Packaging (PyInstaller) and Testing

> **Reality check against the POC (`biscuit.py` + `Biscuit.spec`):**
> - **No bundled assets, so no asset-path trap.** The dog is procedural — `Biscuit.spec` has
>   `datas=[]` and there is **no `resource_path`/`_MEIPASS` helper** in the code. §1–§2 below
>   only become relevant if you add PNG/JSON assets later.
> - **No `%APPDATA%` settings file.** The only thing persisted is a **Windows Run registry key**
>   under `HKCU\...\CurrentVersion\Run` (via `winreg`) for "Launch at startup". The menu toggles
>   (Pause, Stretch reminders, Water reminders) are **in-memory only** and reset on restart. See
>   §0 for the real startup mechanism; ignore the §5 "settings persist to `%APPDATA%`" item.
> - **The Test menu exists and matches** (it's a flat section, not a submenu): Test stretch,
>   water, fetch, scratch, chew, sniff. There is **no `--test` CLI flag and no screenshot
>   helper** in the code (§4 is aspirational).
> - The real `Biscuit.spec` builds a one-file, windowed exe with `upx=True` and **no icon set**.

Two jobs here: ship the `.exe`, and verify behavior without waiting on 30/60-minute timers. The
right-click **Test menu** (which the POC has) is how you fire any behavior on demand.

---

## 0. What the POC actually packages and persists

- **Spec (`Biscuit.spec`):** `Analysis(['biscuit.py'], datas=[], ...)`, `PYZ`, then a single
  `EXE(...)` with `name='Biscuit'`, `console=False` (no console window), `upx=True`,
  `runtime_tmpdir=None`, and no `icon=`. It's the default one-file PyInstaller layout with no
  added data — correct, because there are no assets to bundle.

  ```bash
  pyinstaller --noconfirm Biscuit.spec
  ```

- **Startup persistence = registry, not a settings file.** "Launch at startup" reads/writes the
  `Biscuit` value under `HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\Run`:

  ```python
  def _exe_path(self):
      if getattr(sys, "frozen", False):          # running as the PyInstaller exe
          return f'"{sys.executable}"'
      return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'  # running as .py

  # enable: winreg.SetValueEx(k, "Biscuit", 0, winreg.REG_SZ, self._exe_path())
  # disable: winreg.DeleteValue(k, "Biscuit")
  ```

  Note it does use the `sys.frozen` / `sys.executable` check (the one genuinely
  packaging-aware bit of the code) so the registry command is correct whether run as a script
  or as the frozen exe.

- **No other persisted state.** Menu toggles live on the instance and reset each launch.

---

## 1. The PyInstaller asset-path trap (read before the first build)

In dev, `assets/dog.png` resolves against the current directory. Once frozen with PyInstaller's
one-file mode, the app unpacks to a temp dir and the path breaks. Resolve every asset path
through this helper:

```python
import sys, os

def resource_path(rel):
    # PyInstaller one-file sets sys._MEIPASS to the temp unpack dir
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel)

# usage
QPixmap(resource_path("assets/dog_walk.png"))
manifest = json.load(open(resource_path("assets/assets.json"), encoding="utf-8"))
```

Use `resource_path` for **read-only bundled assets** (sprites, manifest). For files the app
**writes** (settings, saved state), do not use `_MEIPASS`; write to a real user dir:

```python
appdata = os.path.join(os.environ["APPDATA"], "Persi")
os.makedirs(appdata, exist_ok=True)
settings_file = os.path.join(appdata, "settings.json")
```

---

## 2. Bundling assets into the exe

Two routes. The spec file is cleaner and reproducible.

### Quick one-liner

```bash
pyinstaller --noconfirm --onefile --windowed ^
  --add-data "assets;assets" ^
  --name Persi main.py
```

- `--windowed` (a.k.a. `--noconsole`): no console window pops up behind the overlay.
- `--add-data "assets;assets"`: bundle the folder. On Windows the separator is `;`
  (it's `:` on macOS/Linux). This is a common copy-paste bug.
- `--onefile`: single exe (what the POC ships).

### Spec file (preferred — commit it)

```python
# build.spec
block_cipher = None
a = Analysis(
    ['main.py'],
    pathex=['.'],
    datas=[('assets', 'assets')],   # (source, dest-inside-bundle)
    hiddenimports=[],
    hookspath=[], runtime_hooks=[], excludes=[],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='Persi', console=False, onefile=True,
    icon='assets/persi.ico',
)
```

```bash
pyinstaller --noconfirm build.spec
```

### Build cadence

Don't rebuild the exe for every behavior tweak; run `python main.py` directly while iterating.
Rebuild the exe only to verify packaging (asset loading, icon, no console). PyInstaller builds
are slow; the dev run is instant.

### PyInstaller gotchas

- **Antivirus false positives** on one-file exes are common. If Defender quarantines it, that's
  the packer, not your code; an unsigned hobby exe will trip this. Code-signing fixes it long
  term.
- **First launch is slow** with `--onefile` (it unpacks to temp each run). If startup lag
  bothers you, use `--onedir` instead and ship the folder.
- Verify the **icon** shows on the exe and that **no console window** flashes.

---

## 3. The right-click settings + Test menu

Keep a `QMenu` on right-click with two sections: user toggles and a **Test** submenu that fires
every behavior instantly. This is the on-demand way to reproduce timed behaviors.

```python
from PyQt5.QtWidgets import QMenu

def show_menu(self, global_pos):
    m = QMenu()

    # toggles
    for name in ["Stretch reminders", "Water reminders", "Cursor proximity", "Ambient wandering"]:
        a = m.addAction(name); a.setCheckable(True)
        a.setChecked(self.settings[name]); a.toggled.connect(lambda v, n=name: self.set_toggle(n, v))

    m.addSeparator()

    # test triggers — one per behavior, fires immediately
    test = m.addMenu("Test")
    for label, beh in [
        ("Normal walk", NormalWalk), ("Sniff walk", SniffWalk), ("Scratch", Scratch),
        ("Chew bone", ChewBone), ("Stretch", StretchReminder), ("Water", WaterReminder),
        ("Fetch", Fetch), ("Excited", Excited),
    ]:
        test.addAction(label).triggered.connect(lambda _, b=beh: self.scheduler.trigger(b()))

    m.addSeparator()
    m.addAction("Quit").triggered.connect(self.quit)
    m.exec_(global_pos)
```

Every behavior you add gets a matching test entry. That's the contract: if it can't be triggered
from the Test menu, it can't be verified on demand.

---

## 4. Screenshot-based verification (the "eyes")

A browser game can be driven by Playwright. A native overlay can't, but you can still verify
visually: trigger a behavior, grab a screenshot, and inspect the sprite region.

```python
# capture the overlay region to a PNG for inspection
from PyQt5.QtWidgets import QApplication
screen = QApplication.primaryScreen()
shot = screen.grabWindow(0, x, y, w, h)   # 0 = whole desktop; crop to the pet's rect
shot.save("verify/scratch_frame.png")
```

A practical loop when building with an AI agent:
1. Fire a behavior from the Test menu (or a temporary CLI flag like `python main.py --test scratch`).
2. Capture the sprite region to `verify/<behavior>.png`.
3. Open the PNG and confirm the pose/animation looks right (the agent can read the image).
4. For regressions, diff against a known-good capture (pixel diff) and flag large deltas.

Add a `--test <behavior>` startup flag so a behavior can be launched and captured headlessly
without clicking through menus. That's the closest native analog to automated game testing.

---

## 5. Pre-ship checklist (annotated for the POC)

- [ ] Runs from `python biscuit.py` with every behavior reachable via the Test menu. ✔ matches.
- [ ] One-file, windowed exe (`pyinstaller Biscuit.spec`) launches with no console and the dog
      on the taskbar. (No icon is set today; add `icon=` to the spec if you want one.)
- [ ] Click-through verified: desktop/taskbar clickable everywhere except the dog/objects
      (provided by the per-frame window mask — see overlay-window.md §3).
- [ ] "Launch at startup" toggles the `HKCU\...\Run\Biscuit` registry value correctly both as a
      script and as the frozen exe.
- [ ] ~~All assets load through `resource_path`~~ — N/A: no bundled assets (procedural drawing).
- [ ] ~~Settings persist to `%APPDATA%`~~ — N/A: only the startup registry key persists; toggles
      are in-memory by design.
- [ ] ~~Screenshot capture of each behavior~~ — not implemented; verify visually by eye for now.
