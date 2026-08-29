"""macOS Input Monitoring permission pre-flight.

pynput's listeners use a passive CGEventTap, which macOS gates behind the
**Input Monitoring** ("Listen Event") privacy permission. Without it, the tap is
installed but never receives events — so the recorder would silently produce
empty files. This module checks that state up front and gives the user clear,
actionable instructions instead.

Uses the CoreGraphics preflight/request APIs (macOS 10.15+), exposed via Quartz:
- CGPreflightListenEventAccess() -> already granted?
- CGRequestListenEventAccess()   -> prompt + add this app to the list
"""

from __future__ import annotations

import subprocess

# System Settings deep-link for the Input Monitoring pane.
_INPUT_MONITORING_PANE = (
    "x-apple.systempreferences:com.apple.preference.security"
    "?Privacy_ListenEvent"
)


def check_input_monitoring() -> bool | None:
    """True if granted, False if not, None if it can't be determined
    (e.g. older macOS or missing API)."""
    try:
        from Quartz import CGPreflightListenEventAccess
        return bool(CGPreflightListenEventAccess())
    except Exception:
        return None


def request_input_monitoring() -> bool | None:
    """Trigger the one-time system prompt and add this process to the Input
    Monitoring list (initially unchecked). Returns the resulting state, or None
    if the API is unavailable."""
    try:
        from Quartz import CGRequestListenEventAccess
        return bool(CGRequestListenEventAccess())
    except Exception:
        return None


def open_input_monitoring_settings() -> None:
    """Open System Settings directly on the Input Monitoring pane."""
    try:
        subprocess.run(["open", _INPUT_MONITORING_PANE], check=False)
    except Exception:
        pass


def _instructions() -> str:
    return (
        "This tool needs the macOS 'Input Monitoring' permission to capture "
        "keyboard/mouse events.\n\n"
        "  1. In the window that just opened (System Settings > Privacy & "
        "Security > Input Monitoring),\n"
        "     enable the checkbox next to your terminal / IDE (the app running "
        "Python).\n"
        "  2. If it isn't listed, click '+' and add it, or re-run this command "
        "to trigger the prompt.\n"
        "  3. Fully QUIT and reopen that terminal / IDE (the permission only "
        "takes effect on relaunch).\n"
        "  4. Run the command again.\n\n"
        "Optional: to also capture foreground window titles, grant 'Screen "
        "Recording' the same way.\n"
        "(Without it, the app name is still recorded; the title is left blank.)"
    )


def ensure_input_monitoring() -> bool:
    """Pre-flight the Input Monitoring permission.

    Returns True if recording may proceed (granted, or state unknown so we let
    the OS decide), False if it is known-denied and the caller should abort
    after we've shown instructions and opened the settings pane.
    """
    state = check_input_monitoring()

    if state is True:
        return True

    if state is None:
        # Couldn't determine (older macOS / API missing). Don't block — the
        # listener will still work if the permission happens to be granted.
        print("WARNING: could not verify Input Monitoring permission; "
              "proceeding anyway.")
        print("         If no events are captured, grant 'Input Monitoring' to "
              "your terminal/IDE\n"
              "         in System Settings > Privacy & Security, then relaunch "
              "it.")
        return True

    # Known-denied: prompt, open the pane, and print instructions.
    print("ERROR: Input Monitoring permission is not granted.\n")
    request_input_monitoring()          # registers app + shows the OS prompt
    open_input_monitoring_settings()    # jump straight to the pane
    print(_instructions())
    return False
