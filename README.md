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
| `--plain`      | —   | No       |   —          | Use the plain text reporter instead of the rich live TUI |
| `--mask-keys`  | —   | No       |   —          | Hide typed characters in the live event feed (`SimKey:•;<vk>`) |
| `--demo`       | —   | No       |   —          | Feed synthetic events (preview UI; no permission needed) |
| `--session-id` | —   | No       | generated UUID | Session id recorded in `metadata.session_id` |
| `--task-type`  | —   | No       |   —          | Collection protocol: `free-text`, `fixed-text`, `free-mouse`, … |
| `--prompt-id`  | —   | No       |   —          | Identifier of the prompt/stimulus, if any |

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

On an interactive terminal you get a **rich live TUI** — a header, a time
progress bar, running stats, a recent-flush strip, and a scrolling event feed:

```
╭───────────────────────────── input_recorder ─────────────────────────────╮
│  ● keyboard  →  /Users/you/Data/KBD_JSON   user 'you'                     │
│  ━━━━━━━━━━━━━━━╸━━━━━━━━━━━━━━━━━━━━━━━━ 00:47 / 02:00                    │
│  events 336   files 1   next flush 13s   ·  Ctrl+C to stop                │
│  ╭─ recent ─────────────────────────────────────────────────────────────╮ │
│  │ ✓ wrote you1.json (210 actions)                                       │ │
│  ╰───────────────────────────────────────────────────────────────────────╯ │
│  ╭─ event feed (last 12) ───────────────────────────────────────────────╮ │
│  │    time  action    key / pos            window                        │ │
│  │    0.42  press     SimKey:i;34          Terminal app -:- bash         │ │
│  │    0.55  press     SimKey:vk49;49       Notes app -:- Untitled        │ │
│  ╰───────────────────────────────────────────────────────────────────────╯ │
╰───────────────────────────────────────────────────────────────────────────╯
```

The run ends with a summary (`✔ Recording complete — N events, M files …`),
and a warning if **zero** events were captured — the tell-tale sign macOS is
blocking the event tap.

- **`--plain`** falls back to a dependency-free carriage-return status line plus
  `✓ wrote …` log lines. This is also used **automatically** when stdout isn't a
  TTY (pipes / CI / redirected logs), so output stays clean there.
- **`--mask-keys`** replaces the typed character in the feed with `•`
  (`SimKey:•;<vk>`) so the on-screen feed doesn't reveal exactly what was typed —
  worth considering for a keystroke tool. It affects the **display only**; the
  JSON files always contain the real labels.

### Previewing the UI (`--demo`)

Want to see the live TUI without granting permissions or typing? `--demo` feeds
**synthetic** events through the exact same pipeline (buffering, flushing, JSON
output, and the live display animate normally):

```bash
python -m input_recorder -d ~/Data -r 30 -i 5 --demo            # keyboard TUI
python -m input_recorder -d ~/Data -r 30 -i 5 -t mouse --demo   # mouse TUI
```

No Input Monitoring permission is needed in demo mode. It also doubles as a
non-interactive smoke test — under `--plain` / a pipe it still exercises the
whole path and writes real JSON files (with a `DemoApp app -:- synthetic input`
window context so demo data is obvious).

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
    "collection": { "task_type": "free-text", "prompt_id": null },
    "device": {                  // environment (Shen 2013; Ahmed & Traore 2007)
      "keyboard_layout": "com.apple.keylayout.US",
      "os": "macOS-26.4-arm64-...", "os_version": "26.4",
      "primary_screen": { "width_px": 1512, "height_px": 982, "scale": 2.0 },
      "python": "3.14.7"
    },
    "file_write_interval": 60,
    "monitor_info": [ ... ],     // mouse only — see below
    "number_of_actions": 617,
    "quality": { "out_of_order_events": 0 },
    "sampling_rate_hz": 61.4,    // mouse only — observed move rate
    "session_id": "deac3702-...",// stable across a session's files
    "session_start": 1780383649.5,
    "signal_type": "keyboard",   // or "mouse"
    "timestamp": 1780383709.18,  // epoch seconds at flush time
    "timing": {                  // timing provenance (Killourhy & Maxion 2009)
      "backend": "pynput", "source": "monotonic_callback",
      "unit": "s", "clock_resolution_ms": 0.00004
    },
    "version": "2"
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
├── device_info.py       # device/screen/layout metadata (macOS-specific)
├── permissions.py       # Input Monitoring pre-flight (macOS-specific)
├── reporting.py         # rich TUI + plain reporter    (macOS-specific)
├── console.py           # low-level carriage-return line writer
├── demo.py              # synthetic event source for --demo
└── json_writer.py       # buffering + JSON output     (≈ json_writer.cpp)
```
