"""Device / environment metadata for the recording session.

Behavioral-biometrics features are only comparable across recordings taken on a
consistent device (Shen et al., IEEE TIFS 2013; Ahmed & Traore, IEEE TDSC 2007).
This captures the environment so consumers can filter/segment by device, screen,
and keyboard layout. Every field is best-effort — anything unavailable is null.
"""

from __future__ import annotations

import platform
import subprocess
import time

try:
    import Quartz
    _HAVE_QUARTZ = True
except Exception:  # pragma: no cover
    _HAVE_QUARTZ = False

try:
    from AppKit import NSScreen
    _HAVE_APPKIT = True
except Exception:  # pragma: no cover
    _HAVE_APPKIT = False


def _primary_screen() -> dict | None:
    if not _HAVE_QUARTZ:
        return None
    try:
        mid = Quartz.CGMainDisplayID()
        screen = {
            "width_px": int(Quartz.CGDisplayPixelsWide(mid)),
            "height_px": int(Quartz.CGDisplayPixelsHigh(mid)),
            "scale": None,
        }
        if _HAVE_APPKIT:
            try:
                screen["scale"] = float(NSScreen.mainScreen().backingScaleFactor())
            except Exception:
                pass
        return screen
    except Exception:
        return None


def _keyboard_layout() -> str | None:
    """Best-effort current keyboard layout id (e.g. com.apple.keylayout.US).
    TIS APIs aren't reliably exposed via pyobjc, so read HIToolbox prefs."""
    try:
        out = subprocess.run(
            ["defaults", "read",
             "com.apple.HIToolbox", "AppleCurrentKeyboardLayoutInputSourceID"],
            capture_output=True, text=True, timeout=2)
        value = out.stdout.strip()
        return value or None
    except Exception:
        return None


def clock_resolution_ms() -> float:
    """Resolution of the monotonic clock, in milliseconds."""
    try:
        return time.get_clock_info("monotonic").resolution * 1000.0
    except Exception:
        return 0.0


def build_device_info() -> dict:
    return {
        "keyboard_layout": _keyboard_layout(),
        "os": platform.platform(),
        "os_version": platform.mac_ver()[0] or None,
        "primary_screen": _primary_screen(),
        "python": platform.python_version(),
    }
