# Reconciliation Notes — skill vs. real code

Date: 2026-06-05 · Branch: `skill-migration` · Scope: docs only (no application code changed).

I installed the `transparent-desktop-app` skill into `.claude/skills/` and reconciled its docs
against the actual `biscuit.py` / `Biscuit.spec`. **Where the working POC and the skill
disagreed, the code won** and the skill text was corrected. Below: what the skill assumed, what
the code actually does, and which lines I changed.

Files edited (only these, plus this notes file):
- `.claude/skills/transparent-desktop-app/references/overlay-window.md`
- `.claude/skills/transparent-desktop-app/references/sprites-and-animation.md`
- `.claude/skills/transparent-desktop-app/references/assets-and-behaviors.md`
- `.claude/skills/transparent-desktop-app/references/packaging-and-testing.md`
- `.claude/skills/transparent-desktop-app/SKILL.md`

No application source was touched. No exe was rebuilt.

---

## 1. Click-through method (the biggest difference)

- **Skill assumed:** click-through via a **Win32 input-transparency toggle**
  (`WS_EX_LAYERED | WS_EX_TRANSPARENT`) flipped on/off by **polling the cursor**; the window-mask
  approach was labeled as stuttering/discouraged for animation.
- **Code actually does:** a **per-frame `setMask(QRegion)`**. `_update_mask()`
  ([biscuit.py:189](biscuit.py#L189)) unions the dog's current bounding rect with the decor rect
  (and the ball when thrown) and is rebuilt every tick from `_on_tick`
  ([biscuit.py:255](biscuit.py#L255)). There is **no** `WS_EX_TRANSPARENT`/`WS_EX_LAYERED` code
  and no cursor-poll-based toggle anywhere. Clicks are routed in `mousePressEvent`
  ([biscuit.py:597](biscuit.py#L597)).
- **Changed:** rewrote `overlay-window.md` §3 to document the mask technique as the real method
  (and demoted the Win32 toggle to "alternative if you switch to heavy bitmap rendering").
  Updated `SKILL.md` "Window model" paragraph and the `WA_TransparentForInput` anti-pattern row.

## 2. Drawing is procedural, not spritesheets

- **Skill assumed:** spritesheets loaded into `QPixmap`, sliced into frames, played by an
  `Animator`/`QElapsedTimer`; "measure the asset, never guess." A manifest (`assets.json`)
  indexing every PNG. References to `Persi-walk.png` / `Persi2-sleep.png`.
- **Code actually does:** the dog is **drawn procedurally** with `QPainter` primitives
  (`_draw_standing` / `_draw_sleeping` etc., [biscuit.py:479](biscuit.py#L479),
  [biscuit.py:530](biscuit.py#L530)). Motion is `math.sin` over phase accumulators
  (`breath_phase`, `tail_phase`, `walk_phase`) advanced each tick. **No PNGs, no `QPixmap`, no
  `assets.json`, no `resource_path`/`_MEIPASS`** — `Biscuit.spec` has `datas=[]`.
- **Changed:** added a "reality check" banner + new §0 ("How the POC actually animates") to
  `sprites-and-animation.md`; corrected the Persi-art note. Added a reality banner + §0 to
  `assets-and-behaviors.md` (no manifest, no `Behavior`/`Scheduler` classes — a `State` enum and
  an `if/elif` dispatch instead). Added reality notes to `packaging-and-testing.md` (no asset
  bundling).

## 3. State machine, persistence, topmost, DPI (smaller corrections)

- **Behavior architecture:** skill described self-contained `Behavior` objects + a `Scheduler`
  with a weighted ~20 s ambient roll. Code uses one `State` enum + `_update_state()` dispatch
  ([biscuit.py:261](biscuit.py#L261)); ambient activity is a **4–8 min single-shot sleep timer**
  that fires `random.choice(('walk','scratch','chew','sniff'))` ([biscuit.py:317](biscuit.py#L317),
  [biscuit.py:339](biscuit.py#L339)). → documented in `assets-and-behaviors.md` §0.
- **Persistence:** skill said settings persist to `%APPDATA%`. Code persists **only a Windows
  `HKCU\...\Run` registry key** for "Launch at startup" ([biscuit.py:985](biscuit.py#L985));
  menu toggles are in-memory. → corrected `packaging-and-testing.md` §0 and §5 checklist.
- **Topmost:** skill said "don't reassert topmost by default." Code **does** — `_assert_topmost`
  calls `SetWindowPos(HWND_TOPMOST, ... SWP_NOACTIVATE)` at startup and every 180 ticks
  ([biscuit.py:209](biscuit.py#L209), [biscuit.py:258](biscuit.py#L258)). → corrected
  `overlay-window.md` §5.
- **DPI / window sizing:** skill enabled `AA_EnableHighDpiScaling` and sized the window to the
  taskbar height. Code **stays in logical pixels** (no high-DPI attribute) and places a fixed
  `WIN_H = 95` px full-width strip **above** the taskbar via `get_taskbar_rect()`
  ([biscuit.py:31](biscuit.py#L31), [biscuit.py:183](biscuit.py#L183)). → corrected
  `overlay-window.md` §1–§2 and §4.
- **Flags/attrs:** code adds `Qt.NoDropShadowWindowHint` + `WA_ShowWithoutActivating` and omits
  `WA_NoSystemBackground`/`WA_AlwaysShowToolTips`. → corrected in `overlay-window.md` §1 and
  `SKILL.md`.

## What the skill already got right (kept as-is)

`Qt.Tool` to stay out of the taskbar/alt-tab; default state = sleeping on the bed; right-click
**Test menu** firing each behavior on demand (the POC has exactly this); stretch=30 min /
water=60 min reminder cadence; clicking the dog/ball/bowl as input triggers; "no `time.sleep`,
drive animation from a `QTimer`."
