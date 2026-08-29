"""Recording session driver — the macOS analog of main.cpp.

Unlike the Win32 version there is no message loop or OS timer: pynput runs its
event tap on its own thread, and the main thread simply polls a monotonic clock
to drive interval flushes and the runtime cutoff. Ctrl+C flushes and exits.
"""

from __future__ import annotations

import os
import sys
import time

from .cli_options import parse_cli_options
from .console import ConsoleReporter, format_mmss
from .displays import enumerate_monitors
from .entity_info import build_entity_info
from .json_writer import RecordingWriter
from .keyboard_listener import KeyboardListener
from .mouse_listener import MouseListener
from .permissions import ensure_input_monitoring

_POLL_INTERVAL_SECONDS = 0.2


def _report_flush(reporter: ConsoleReporter, result: tuple[str, int] | None) -> None:
    if result is not None:
        filename, count = result
        reporter.log(f"  ✓ wrote {os.path.basename(filename)} "
                     f"({count} action{'s' if count != 1 else ''})")


def main(argv: list[str]) -> int:
    options = parse_cli_options(argv)

    # Fail fast with clear instructions if macOS won't let us capture input,
    # rather than silently recording nothing.
    if not options.skip_permission_check and not ensure_input_monitoring():
        return 1

    entity = build_entity_info(
        options.username, options.machine_id, options.tenant, options.tuid)
    username_prefix = entity.user_id

    monitor_info = []
    if options.signal_type == "mouse":
        monitor_info = enumerate_monitors()

    writer = RecordingWriter(
        options.data_dir, options.signal_type, entity,
        options.interval_seconds, monitor_info)

    start = time.monotonic()
    if options.signal_type == "keyboard":
        listener = KeyboardListener(start, writer.add_payload_entry)
    else:
        listener = MouseListener(start, writer.add_payload_entry)

    reporter = ConsoleReporter()
    reporter.log(f"● Recording {options.signal_type}  →  {writer.output_subdir}")
    reporter.log(f"  duration {options.runtime_seconds}s · flush every "
                 f"{options.interval_seconds}s · user '{username_prefix}'")
    reporter.log("  Press Ctrl+C to stop early.")

    try:
        listener.start()
    except Exception as exc:
        reporter.log(f"ERROR: failed to start {options.signal_type} listener ({exc})")
        reporter.log("On macOS, grant Input Monitoring to your terminal in "
                     "System Settings > Privacy & Security, then relaunch it.")
        return 1

    runtime = options.runtime_seconds
    interval = options.interval_seconds
    last_flush = 0.0
    stopped_early = False
    try:
        while True:
            now = time.monotonic() - start
            if now >= runtime:
                break
            if now - last_flush >= interval:
                _report_flush(reporter, writer.flush(username_prefix))
                last_flush = now
            next_flush_in = max(0, int(interval - (now - last_flush)))
            reporter.status(
                f"  ● {format_mmss(now)} / {format_mmss(runtime)}  "
                f"│ events {writer.total_events}  │ files {writer.files_written}  "
                f"│ next flush {next_flush_in}s  │ Ctrl+C to stop")
            time.sleep(_POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        stopped_early = True
    finally:
        reporter.clear()
        listener.stop()
        # Flush anything captured since the last interval boundary.
        _report_flush(reporter, writer.flush(username_prefix))

    elapsed = time.monotonic() - start
    if stopped_early:
        reporter.log("  (stopped early)")
    reporter.log(
        f"✔ Recording complete — {writer.total_events} events, "
        f"{writer.files_written} file{'s' if writer.files_written != 1 else ''} "
        f"in {format_mmss(elapsed)} → {writer.output_subdir}")

    if writer.total_events == 0:
        reporter.log(
            "  ⚠ No events were captured. If you expected input, macOS is "
            "likely blocking\n"
            "    the event tap — grant 'Input Monitoring' to your terminal/IDE "
            "and relaunch it.")
    return 0


def run() -> None:
    """Console-script entry point."""
    sys.exit(main(sys.argv))
