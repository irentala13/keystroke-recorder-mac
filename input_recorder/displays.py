"""Display enumeration — the macOS analog of EnumerateMonitors() (mouse only).

Populated into metadata.monitor_info for mouse recordings. width_mm/height_mm/
name are always null, matching the reference samples (no physical-size lookup).
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import Quartz
    _HAVE_QUARTZ = True
except Exception:  # pragma: no cover
    _HAVE_QUARTZ = False


@dataclass
class MonitorInfo:
    x: int
    y: int
    width: int
    height: int
    is_primary: bool


def enumerate_monitors() -> list[MonitorInfo]:
    if not _HAVE_QUARTZ:
        return []
    monitors: list[MonitorInfo] = []
    try:
        max_displays = 16
        err, active, count = Quartz.CGGetActiveDisplayList(max_displays, None, None)
        if err != 0:
            return []
        main = Quartz.CGMainDisplayID()
        for display_id in list(active)[:count]:
            bounds = Quartz.CGDisplayBounds(display_id)
            monitors.append(MonitorInfo(
                x=int(bounds.origin.x),
                y=int(bounds.origin.y),
                width=int(bounds.size.width),
                height=int(bounds.size.height),
                is_primary=(display_id == main),
            ))
    except Exception:
        return monitors
    return monitors
