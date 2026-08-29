# keystroke-recorder-mac (input_recorder)

A macOS keyboard/mouse recorder — the **macOS counterpart** to the Windows-only
[`keystroke-recorder-win`](../keystroke-recorder-win) C++ tool. It captures
low-level keyboard or mouse input and writes it to JSON files that can be
replayed into a behavioral-biometrics engine for testing.

It keeps the Windows tool's **CLI, output-directory layout, filename pattern,
and JSON structure**, while adapting the platform-specific fields that don't map
cleanly from Windows to macOS (see [Differences](#differences-from-the-windows-tool)).

**This is a QA/test-automation tool**, intended for a tester recording their own
input (or a controlled demo machine) to generate synthetic signal data — not a
general-purpose monitoring tool.

---

## Requirements

- macOS
- Python 3.9+
- [`pynput`](https://pypi.org/project/pynput/) and the PyObjC Cocoa/Quartz
  frameworks (installed via `requirements.txt`)

### macOS permissions (required)

macOS blocks global input capture until you grant permission. Grant these to the
app that launches Python (e.g. **Terminal**, **iTerm**, or your IDE) under
**System Settings › Privacy & Security**:

| Permission          | Needed for                                            |
|---------------------|-------------------------------------------------------|
| **Input Monitoring**| Capturing keystrokes / mouse events (required)        |
| **Screen Recording**| *Optional* — only to capture the foreground **window title**. Without it, the app name is still recorded; the title is left blank. |

After granting, **fully quit and reopen** the terminal/IDE — the permission only
takes effect on relaunch.

#### Automatic pre-flight check

You don't have to remember this. Every run first checks the Input Monitoring
permission (via `CGPreflightListenEventAccess`). If it isn't granted, the tool:

1. prints step-by-step instructions,
2. triggers the macOS permission prompt (registering the app in the list), and
3. opens **System Settings** directly on the Input Monitoring pane,

then exits without recording — so you never silently capture an empty file.
Grant the permission, relaunch your terminal, and run the command again.

Pass `--skip-permission-check` to bypass this and start immediately (useful in
CI or once you know the permission is granted).

## Install

```bash
cd keystroke-recorder-mac
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Same flags as the Windows tool:

```
python -m input_recorder -d <data_dir> [options]
```

| Flag | Long form     | Required | Default      | Description                                          |
|------|---------------|----------|--------------|------------------------------------------------------|
| `-d` | `--data-dir`  | Yes      | —            | Output directory. Files go to `<dir>/KBD_JSON/` or `<dir>/MOUSE_JSON/` |
| `-u` | `--username`  | No       | Current user | Username prefix for output filenames and `entity.user_id` |
| `-r` | `--runtime`   | No       | 60           | Recording duration in seconds                        |
| `-i` | `--interval`  | No       | 60           | File flush interval in seconds                       |
| `-t` | `--type`      | No       | keyboard     | Signal type: `keyboard` or `mouse`                   |
| `--machine-id` | —   | No       | `FAKE_MACHINE_ID` | Placeholder `entity.machine_id`                 |
| `--tenant`     | —   | No       | `FAKE_TENANT`     | Placeholder `entity.tenant`                     |
| `--tuid`       | —   | No       | `FAKE_TUID`       | Placeholder `entity.tuid`                       |
| `--skip-permission-check` | — | No |   —          | Skip the Input Monitoring pre-flight and start recording immediately |

**Examples:**
```bash
# Record keyboard for 2 minutes, flush every 30s
python -m input_recorder -d ~/Data -r 120 -i 30

# Record mouse for 5 minutes
python -m input_recorder -d ~/Data -t mouse -r 300
```

Output filenames follow `<username><N>.json` (e.g. `user1.json`, `user2.json`,
…), incrementing per flush. Press **Ctrl+C** to stop early; the current buffer is
flushed before exit.

If you `pip install .`, the console script `input_recorder` is also available.

### Console output

While recording, a **live status line** updates in place with elapsed/total
time, cumulative events, files written, and the countdown to the next flush:

```
● Recording keyboard  →  /Users/you/Data/KBD_JSON
  duration 120s · flush every 30s · user 'you'
  Press Ctrl+C to stop early.
  ✓ wrote you1.json (210 actions)
  ● 00:47 / 02:00  │ events 331  │ files 1  │ next flush 13s  │ Ctrl+C to stop
```

Each flush prints a persistent `✓ wrote …` line, and the run ends with a summary
(`✔ Recording complete — N events, M files …`). If **zero** events were captured
it prints a warning — the tell-tale sign macOS is blocking the event tap. When
stdout isn't a TTY (pipes/CI), the live line is suppressed and only the log lines
and summary are printed.

---

## JSON schema

```jsonc
{
  "entity": {
    "machine_id": "FAKE_MACHINE_ID",
    "machine_name": "...",       // socket.gethostname()
    "tenant": "FAKE_TENANT",
    "tuid": "FAKE_TUID",
    "user_id": "..."             // -u, or getpass.getuser()
  },
  "metadata": {
    "file_write_interval": 60,
    "monitor_info": [ ... ],     // mouse only — see below
    "number_of_actions": 617,
    "signal_type": "keyboard",   // or "mouse"
    "timestamp": 1780383709.18,  // epoch seconds at flush time
    "version": "1"
  },
  "payload": [
    // keyboard: [action, "SimKey:<label>;<vk_code>", elapsed_seconds, window_context]
    ["press",   "SimKey:a;0",   0.0,   "Terminal app -:- bash"],
    ["release", "SimKey:vk49;49", 0.687, "TextEdit app -:- README md"],

    // mouse — shape varies by action:
    ["move",    [712.6, -160.4],                  0.006, "..."],
    ["click",   [1477.2, -657.8, "Button.left"],  0.527, "..."],
    ["scroll",  [1197.4, -730.0, 0, 0],           1.637, "..."]
  ]
}
```

### Key labeling rule

A single alphanumeric character (`0`-`9`, `a`-`z`) → its literal lowercase form;
every other key (space, punctuation, Return, modifiers, arrows) → `vk<code>`
using the **macOS virtual key code**. The label *shape* matches the Windows tool
so downstream parsing is unchanged.

### `monitor_info`

Populated only for `signal_type: "mouse"`, via Quartz `CGGetActiveDisplayList` /
`CGDisplayBounds`. `width_mm`/`height_mm`/`name` are always `null`, matching the
reference samples.

---

## Differences from the Windows tool

These are deliberate macOS adaptations (the project was scoped as
"macOS-adapted", not byte-for-byte drop-in):

- **Virtual key codes differ.** macOS virtual key codes are not the same numbers
  as Windows VK codes. Alphanumeric labels (`a`, `3`) are identical across
  platforms; the `vk<code>` values for other keys differ.
- **Window context uses `app` instead of `exe`.** Format is
  `"<app name> app -:- <sanitized title>"` (Windows used `"<process> exe -:- …"`).
  App name via `NSWorkspace`; title via Quartz (needs Screen Recording, else blank).
- **Timing source.** Events are timestamped with `time.monotonic()` at callback
  time (relative to recording start), rather than the OS hook's own event time.
  This can include a small amount of scheduling jitter the Win32 version avoids.
- **Mouse coordinates** come from pynput (Quartz global coordinates) and are
  emitted as floats to match the reference payload shape.
- **No admin/root required**, but the macOS **Input Monitoring** (and often
  **Accessibility**) permission must be granted — see above.

## Project layout

```
input_recorder/
├── __main__.py          # python -m input_recorder
├── app.py               # session driver / main loop  (≈ main.cpp)
├── cli_options.py       # argument parsing            (≈ cli_options.cpp)
├── entity_info.py       # entity block                (≈ entity_info.cpp)
├── window_context.py    # foreground app/window       (≈ window_context.cpp)
├── keyboard_listener.py # keyboard capture            (≈ keyboard_hook.cpp)
├── mouse_listener.py    # mouse capture               (≈ mouse_hook.cpp)
├── displays.py          # monitor enumeration         (≈ EnumerateMonitors)
├── permissions.py       # Input Monitoring pre-flight (macOS-specific)
└── json_writer.py       # buffering + JSON output     (≈ json_writer.cpp)
```
