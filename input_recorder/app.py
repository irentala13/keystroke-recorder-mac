"""Recording session driver — the macOS analog of main.cpp.

Unlike the Win32 version there is no message loop or OS timer: pynput runs its
event tap on its own thread, and the main thread simply polls a monotonic clock
to drive interval flushes and the runtime cutoff. Ctrl+C flushes and exits.
"""

from __future__ import annotations

import sys
import time

from .cli_options import parse_cli_options
from .demo import DemoSource
from .displays import enumerate_monitors
from .entity_info import build_entity_info
from .json_writer import RecordingWriter
from .keyboard_listener import KeyboardListener
from .mouse_listener import MouseListener
from .permissions import ensure_input_monitoring
from .reporting import make_reporter

_POLL_INTERVAL_SECONDS = 0.2


def main(argv: list[str]) -> int:
    options = parse_cli_options(argv)

    # Fail fast with clear instructions if macOS won't let us capture input,
    # rather than silently recording nothing. Demo mode fabricates its own
    # events, so it needs no capture permission.
    if (not options.demo and not options.skip_permission_check
            and not ensure_input_monitoring()):
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

    reporter = make_reporter(force_plain=options.plain, mask_keys=options.mask_keys)

    # Tap the capture callback so each event lands in both the JSON buffer and
    # the live feed. Called from the pynput listener thread.
    def on_entry(entry: list) -> None:
        writer.add_payload_entry(entry)
        reporter.event(entry)

    start = time.monotonic()
    if options.demo:
        listener = DemoSource(options.signal_type, start, on_entry)
    elif options.signal_type == "keyboard":
        listener = KeyboardListener(start, on_entry)
    else:
        listener = MouseListener(start, on_entry)

    runtime = options.runtime_seconds
    interval = options.interval_seconds

    with reporter:
        reporter.begin(options.signal_type, writer.output_subdir,
                       runtime, interval, username_prefix)
        if options.demo:
            reporter.note("demo mode: events are synthetic (no real capture)")

        try:
            listener.start()
        except Exception as exc:
            reporter.note(f"ERROR: failed to start {options.signal_type} "
                          f"listener ({exc})")
            reporter.note("Grant Input Monitoring to your terminal in System "
                          "Settings > Privacy & Security, then relaunch it.")
            return 1

        last_flush = 0.0
        stopped_early = False
        try:
            while True:
                now = time.monotonic() - start
                if now >= runtime:
                    break
                if now - last_flush >= interval:
                    reporter.flush_written(writer.flush(username_prefix))
                    last_flush = now
                next_flush_in = max(0, int(interval - (now - last_flush)))
                reporter.update(now, runtime, writer.total_events,
                                writer.files_written, next_flush_in)
                time.sleep(_POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            stopped_early = True
        finally:
            listener.stop()
            # Flush anything captured since the last interval boundary.
            reporter.flush_written(writer.flush(username_prefix))

        elapsed = time.monotonic() - start
        reporter.end(writer.total_events, writer.files_written, elapsed,
                     writer.output_subdir, stopped_early)

    return 0


def run() -> None:
    """Console-script entry point."""
    sys.exit(main(sys.argv))
