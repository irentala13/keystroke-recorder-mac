# Data collection for behavioral biometrics

This recorder targets the **signal-collection** stage of a keystroke/mouse
dynamics pipeline (model training lives in a separate project). The schema and
capture choices follow established IEEE data-collection practice so the raw
recordings are suitable for downstream feature extraction without re-recording.

## Guiding references

- **Killourhy & Maxion, "Comparing Anomaly-Detection Algorithms for Keystroke
  Dynamics," IEEE/IFIP DSN 2009** — timing source and clock resolution
  materially affect error rates; capture key-down and key-up separately with an
  accurate, declared clock.
- **Ahmed & Traore, "A New Biometric Technology Based on Mouse Dynamics,"
  IEEE TDSC 2007** — mouse signal = stream of (x, y, time, action-type)
  including movement, click, drag, and silence/pause; screen context matters.
- **Shen, Cai, Guan, Du & Maxion, "User Authentication Through Mouse Dynamics,"
  IEEE TIFS 2013** — device/environment consistency and procedural control.

> Principle: record **raw events**, derive features **offline**. Never bake
> feature choices into the recorder.

## Schema → feature mapping

| Recorded field | Enables (downstream feature) | Reference |
|---|---|---|
| `payload` `press`/`release` per key + `elapsed` | Key hold time (dwell); DD/UD/DU/UU latencies; n-graph timing | Killourhy-Maxion |
| `payload` mouse `move` `[x,y]` + `elapsed` | Velocity, acceleration, jerk, curvature, path efficiency | Ahmed-Traore |
| `payload` mouse `click`/`release` + button | Click dwell, double-click interval, drag duration | Ahmed-Traore |
| `metadata.timing` (`source`, `unit`, `clock_resolution_ms`) | Trust/normalize timing across recordings | Killourhy-Maxion |
| `metadata.sampling_rate_hz` (mouse) | Resampling / uniform-Δt kinematics | Ahmed-Traore |
| `metadata.device.primary_screen` + `monitor_info` | Coordinate normalization across displays | Ahmed-Traore |
| `metadata.device.keyboard_layout` | Key-identity comparability across machines | Shen 2013 |
| `metadata.session_id` / `session_start` | Per-session windowing; multi-session template aging | surveys |
| `metadata.collection.task_type` / `prompt_id` | Fixed-text vs free-text vs free-mouse segmentation | keystroke surveys |
| `metadata.quality.out_of_order_events` | Detect capture anomalies before training | — |

## Status vs. the literature bar

**Implemented (metadata layer):** session identity, timing provenance,
device/screen/layout, collection protocol, mouse sampling rate, out-of-order
counter. Schema `version` is `2`.

**Pending (capture layer — next):** the biggest literature-critical gap is
**event-sourced, high-resolution timestamps**. pynput times events at the
Python callback (`timing.source = "monotonic_callback"`), which admits scheduler
jitter at the millisecond scale that keystroke dwell/latency features are most
sensitive to. The planned `CGEventTap` backend will read the OS event timestamp
(`CGEventGetTimestamp`) and the auto-repeat flag (`kCGKeyboardEventAutorepeat`),
flipping `timing.source` to `"cgevent_timestamp"` and adding an
`autorepeat`-filtered capture path.

## Collection protocol tips

- Record **multiple sessions per subject across different days** (template aging).
- Keep the **same physical keyboard/mouse** within a subject's sessions.
- Tag each run with `--task-type` and a stable `--session-id` per sitting.
- For free-text keystroke and free mouse, collect **thousands of events** per
  subject; for fixed-text, many repetitions of the same prompt.
