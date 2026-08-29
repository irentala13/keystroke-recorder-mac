"""Foreground-window context — the macOS analog of window_context.cpp.

Windows produced "<process> exe -:- <sanitized title>". macOS has no ".exe",
so this produces "<app name> app -:- <sanitized title>" (a deliberate,
documented macOS adaptation).

The frontmost application name comes from NSWorkspace and always works. The
window *title* comes from the Quartz window list and requires the Screen
Recording permission — without it the title is empty (best-effort), which does
not stop recording.
"""

from __future__ import annotations

try:
    import Quartz
    from AppKit import NSWorkspace
    _HAVE_APPKIT = True
except Exception:  # pragma: no cover - only on non-mac / missing pyobjc
    _HAVE_APPKIT = False


def _sanitize(text: str) -> str:
    """Replace every non-alphanumeric, non-whitespace char with a space, to
    match the sanitized titles seen in real recordings from the pipeline."""
    return "".join(c if (c.isalnum() or c.isspace()) else " " for c in text)


def _frontmost_window_title(pid: int) -> str:
    """Best-effort title of the frontmost on-screen window owned by ``pid``.
    Returns "" if the title is unavailable (e.g. Screen Recording not granted)."""
    try:
        options = (Quartz.kCGWindowListOptionOnScreenOnly
                   | Quartz.kCGWindowListExcludeDesktopElements)
        windows = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        for w in windows or []:
            if w.get("kCGWindowOwnerPID") != pid:
                continue
            # Layer 0 is the normal application window layer.
            if w.get("kCGWindowLayer", 1) != 0:
                continue
            return _sanitize(w.get("kCGWindowName", "") or "")
    except Exception:
        pass
    return ""


def get_frontmost_window_context() -> str:
    if not _HAVE_APPKIT:
        return "Unknown app -:- Unknown"
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return "Unknown app -:- Unknown"
        app_name = app.localizedName() or "Unknown"
        title = _frontmost_window_title(app.processIdentifier())
        return f"{app_name} app -:- {title}"
    except Exception:
        return "Unknown app -:- Unknown"
