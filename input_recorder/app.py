"""Recording session driver — the macOS analog of main.cpp.

Unlike the Win32 version there is no message loop or OS timer: pynput runs its
event tap on its own thread, and the main thread simply polls a monotonic clock
to drive interval flushes and the runtime cutoff. Ctrl+C flushes and exits.
"""

from __future__ import annotations

import sys
import time

from .cli_options import parse_cli_options
from .displays import enumerate_monitors
from .entity_info import build_entity_info
from .json_writer import RecordingWriter
from .keyboard_listener import KeyboardListener
from .mouse_listener import MouseListener

_POLL_INTERVAL_SECONDS = 0.2


def main(argv: list[str]) -> int:
    options = parse_cli_options(argv)

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

    subdir = "KBD_JSON" if options.signal_type == "keyboard" else "MOUSE_JSON"
    print(f"Recording {options.signal_type} for {options.runtime_seconds}s, "
          f"flushing every {options.interval_seconds}s, output: "
          f"{options.data_dir}/{subdir}")
    print("Press Ctrl+C to stop early.")

    try:
        listener.start()
    except Exception as exc:
        print(f"ERROR: failed to start {options.signal_type} listener ({exc})")
        print("On macOS, grant Input Monitoring (and Accessibility) to your "
              "terminal in System Settings > Privacy & Security.")
        return 1

    last_flush = 0.0
    try:
        while True:
            now = time.monotonic() - start
            if now >= options.runtime_seconds:
                break
            if now - last_flush >= options.interval_seconds:
                writer.flush(username_prefix)
                last_flush = now
            time.sleep(_POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        # Flush anything captured since the last interval boundary.
        writer.flush(username_prefix)

    print("Recording complete.")
    return 0


def run() -> None:
    """Console-script entry point."""
    sys.exit(main(sys.argv))
