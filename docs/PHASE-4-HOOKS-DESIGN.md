# Phase 4b/4c Design — Type-along & Bark-at-new-window (DEFERRED, not built)

Status: **design only, by decision 2026-06-11.** The two OS-hook enablers (global keyboard
activity listener, window event hook) are antivirus- and privacy-sensitive, so they are specified
here for later development instead of being built now. Phase 4a (roll-over mouse gesture) was
built and shipped — it needs no hook. Everything in this document plugs into machinery that
already exists: the settings store (Phase 2), the grouped menu, the Test section, the HUD, and
the state machine.

---

## Shared principles for both features

1. **Activity only, never content.** The app may know *that* something happened (a key went
   down; a window appeared) and *when* — never *what* (which key, what title/contents beyond the
   filtering checks). Discard everything else at the lowest level, inside the callback,
   before any queuing.
2. **Off by default.** Both ship with their settings key `False`. The user opts in via the menu.
3. **Plain disclosure in-app.** The first time either toggle is switched on, show a small plain
   `QMessageBox` (one per feature, "don't show again" persisted):
   - Type-along: *"Persi will notice that you are typing and how fast — nothing else. It never
     records, stores, or sends which keys you press."*
   - Bark: *"Persi will notice when a new app window opens, so it can bark once. It does not
     read window contents."*
4. **Each enabler is its own module** (`keyboard_activity.py`, `window_events.py`), imported
   lazily only when its toggle turns on, fully unloadable: turning the toggle off must call the
   module's `stop()` and unhook. Quit must unhook (also via `QApplication.aboutToQuit`).
5. **Fail soft.** If a hook fails to install (permissions, AV interference), revert the toggle
   to off, log once, and show a one-line notice. Never crash, never retry-loop.
6. **One sub-branch per feature** (`feature/phase-4b-type-along`, `feature/phase-4c-bark`),
   verified independently, with its own report section, exe rebuild, and tag.
7. **Code signing before distribution.** Unsigned one-file PyInstaller exes containing a
   keyboard hook are near-guaranteed AV flags. These features should ship only in a signed
   build (Phase 8). For dev, expect to whitelist the exe in Defender.

---

## 4b — Type-along mode (typewriter)

### UX

A **Mode** (sustained, toggled): when on and the user types, Persi trots a few steps toward
screen center, a tiny typewriter prop appears in front of it, and it "types along" — front paws
tapping in rhythm with the user's typing rate, little carriage jitter, an occasional paper
nudge. When the user pauses (>2 s) Persi pauses, paw hovering. When the user stops (>8 s),
Persi nudges the typewriter away (it disappears) and plods back to bed.

### Enabler: keyboard ACTIVITY detector

Two implementation options, in order of preference:

**Option A (preferred): Raw Input (`RegisterRawInputDevices`)** — registers for
`RIDEV_INPUTSINK` keyboard raw input on a message-only window. Receives `WM_INPUT` in our own
process without installing anything into other processes. Friendlier to AV than a low-level
hook and impossible to block other apps' input with. Caveat: needs a native window procedure —
in Qt, override `QWidget.nativeEvent()` (or a `QAbstractNativeEventFilter`) on a hidden window
to catch `WM_INPUT`, then **immediately reduce the event to a timestamp**:

```python
# inside nativeEvent: msg.message == WM_INPUT
#   -> do NOT call GetRawInputData for the key code at all;
#      the arrival of WM_INPUT from a keyboard device IS the activity signal
self._detector.on_activity(time.monotonic())
```

(If distinguishing key-down from key-up turns out to be necessary for rhythm quality, call
`GetRawInputData`, read only `RAWKEYBOARD.Flags` (down/up), and explicitly never read
`VKey`/`MakeCode`; zero the buffer after.)

**Option B (fallback): low-level hook `SetWindowsHookExW(WH_KEYBOARD_LL, ...)`** via ctypes.
The classic approach; works everywhere but is exactly what AV heuristics look for.
Requirements if used:
- The callback must always `return CallNextHookEx(...)` fast (<1 ms); a slow callback lags the
  whole system's keyboard.
- Install on the main thread (Qt already pumps messages, which the LL hook requires).
- In the callback, look only at `wParam == WM_KEYDOWN`; **do not dereference the KBDLLHOOKSTRUCT
  beyond that** (the vkCode field is never read), then just record `time.monotonic()`.
- `UnhookWindowsHookEx` on stop/quit. Keep the `HOOKPROC` ctypes object referenced for the
  hook's lifetime (GC'ing it crashes).

### The detector module (`keyboard_activity.py`)

```python
class TypingActivityDetector(QObject):
    typing_started = pyqtSignal()        # first key after idle
    typing_paused  = pyqtSignal()        # >2 s without a key
    typing_stopped = pyqtSignal()        # >8 s without a key
    rate_changed   = pyqtSignal(float)   # keys/sec, EMA-smoothed

    def start(self) -> bool: ...         # install; False if install failed
    def stop(self): ...                  # uninstall; idempotent
```

- Internals: a ring of recent timestamps only (cap ~32). Rate = EMA over inter-key intervals,
  updated at most ~4×/s (throttled — don't emit per keystroke).
- The pause/stop thresholds (2 s / 8 s) checked from the app's existing 33 ms tick, not a new
  timer.
- **Auditability guarantee:** the module must contain no storage, no file/network access, and
  no reference to key identity. Keep it under ~150 lines so it can be read in one sitting —
  that's the privacy review story.

### Behavior wiring

- New state `TYPE_ALONG` (a Mode state) + `ANIMATION[TYPE_ALONG] = "typewrite"`.
- Enter: on `typing_started`, if mode toggle on and state in (SLEEPING, ALERT): walk
  (trot-brisk) to a typing spot (e.g. `bed_cx - 150`), spawn typewriter prop.
- During: paw-tap cycle speed proportional to `rate_changed` (clamp 1–8 taps/s); `typing_paused`
  freezes the tap mid-cycle; `typing_stopped` exits.
- Exit: nudge animation (~0.5 s), prop despawns, TASK_RETURN (plod) home.
- Interruptions: dog click → EXCITED cancels the mode episode (prop despawns instantly);
  reminders queue (TYPE_ALONG joins the `_check_pending` refusal list) and fire after exit.
- Prop drawing: `_draw_typewriter(p, x, base)` — body rect ~26×10, keybank ellipses, a paper
  rect that grows a few px per burst, carriage that shifts 1 px per tap and resets.
  **Mask:** the typewriter rect must be unioned into `_update_mask` while visible.

### Settings / menu / HUD / tests

- Key: `modes.type_along` (default **False**). Menu: new **Modes** group, label
  "Type along (notices typing only — never which keys)".
- HUD: new line `KEYS` → `idle` / `3.4/s typing` / `paused` — proves live detection and that
  only a rate is known.
- Test entries (work without the hook): "Test: type-along start" (synthesizes
  `typing_started` + a fake 4/s rate) and firing it again ends the episode. The detector itself
  gets a dev script `tools/verify_typealong.py` that uses `SendInput` to synthesize harmless
  key events (e.g. F15) and asserts: episode starts, rate tracks, pause/stop transitions fire,
  uninstall works, and a `git grep` audit that `vkCode`/`VKey` never appears in a read context.

### Acceptance criteria

Typing in any app starts the episode in <1 s; the tap rhythm visibly tracks fast vs slow
typing; pausing/stopping behaves per thresholds; toggle off uninstalls the hook (verify with
`tasklist`-level sanity + repeated on/off cycles, no handle leaks); CPU unchanged at idle;
disclosure shown once; everything force-fireable from Test without the hook installed.

---

## 4c — Bark at new window

### UX

A **Reactive** behavior: when a new top-level application window opens, Persi stands, gives a
short head-back bark (~1 s, 2 bobs), then settles. A burst of windows yields ONE bark.

The bark animation itself (`BARKING` state, `ANIMATION = "bark"`) is **built in Phase 5**
(it's also greet's flourish), so this feature only needs the detector + wiring.

### Enabler: window-creation detector

**Option A (preferred): `SetWinEventHook` (out-of-context)** via ctypes:

```python
hook = user32.SetWinEventHook(
    EVENT_OBJECT_SHOW, EVENT_OBJECT_SHOW,     # 0x8002, window became visible
    0, WINEVENTPROC(callback), 0, 0,
    WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS)
```

- `WINEVENT_OUTOFCONTEXT` = no DLL injection into other processes (the low-AV-risk variant);
  events arrive on our own message loop (Qt pumps it).
- Callback filter, in order (cheap → expensive), all via ctypes `user32`:
  1. `idObject == OBJID_WINDOW and idChild == 0`, hwnd != 0
  2. `GetAncestor(hwnd, GA_ROOT) == hwnd` (true top-level)
  3. `IsWindowVisible(hwnd)`
  4. extended style: no `WS_EX_TOOLWINDOW`; style has `WS_CAPTION` (filters tooltips,
     popups, helper windows)
  5. `GetWindowTextLengthW(hwnd) > 0` (length only — **the title text itself is never read**)
  6. `DwmGetWindowAttribute(DWMA_CLOAKED) == 0` (filters UWP ghost windows)
  7. hwnd not seen in the last 60 s (LRU of hwnd ints — hwnds are reused, hence the expiry)
- `UnhookWinEvent` on stop/quit; keep the WINEVENTPROC reference alive.

**Option B (fallback): polled diff** — every ~2 s, `EnumWindows`, apply filters 2–6, diff the
hwnd set against the previous poll. No hook at all (zero AV surface), at the cost of up to 2 s
latency and a little steady CPU. Good first implementation to validate the filters; the event
hook can replace it later behind the same module API.

### Module API (`window_events.py`)

```python
class NewWindowDetector(QObject):
    window_appeared = pyqtSignal()       # already filtered AND rate-limited

    def start(self) -> bool: ...
    def stop(self): ...
```

Rate limiting lives in the detector: a 8 s refractory period after each emission, plus burst
collapse (events within 1.5 s of each other count as one). The app side stays dumb:
`window_appeared -> if settings and state interruptible: _start_bark()`.

### Settings / menu / HUD / tests

- Key: `reactive.bark_new_window` (default **False**). Menu: Reactive group, label
  "Bark when a new window opens".
- HUD: new line `WINEVT` → `-` / `window +1 (barked)` / `suppressed (rate)` with a 2 s decay,
  so filtering and rate limiting are observable.
- Test: "Test: bark" exists from Phase 5 (fires the animation). The detector gets
  `tools/verify_bark.py`: opens real windows (`notepad.exe`), asserts one bark; opens three
  in quick succession, asserts still one bark; opens a tool-window (a Qt `Qt.Tool` window),
  asserts no bark; toggles off, opens notepad, asserts nothing.

### Acceptance criteria

Opening one normal app barks once within 2 s; a burst barks once; tooltips/tool windows/our own
windows never bark; toggle on/off installs/uninstalls cleanly across repeated cycles; idle CPU
unchanged (Option A) or <1% added (Option B); never interrupts a one-shot (goes through the
same pending/interruptible discipline as reminders).

---

## Privacy stance (to ship in-app, verbatim)

> Persi reacts to *that* you type and *that* windows open — never to what you type or what is
> in your windows. Nothing is recorded, stored, or sent anywhere. Both features are off unless
> you turn them on, and the code that watches for activity is a single small file you (or
> anyone) can read.

## Build order when resumed

1. `feature/phase-4c-bark` first with the **polled** detector (no hook at all) — lowest risk,
   validates filters and wiring end to end.
2. Swap in `SetWinEventHook` behind the same module API.
3. `feature/phase-4b-type-along` with Raw Input (Option A); LL hook only if Raw Input proves
   insufficient.
4. Re-run all phase harnesses + a Defender scan of the rebuilt exe before merging each.
