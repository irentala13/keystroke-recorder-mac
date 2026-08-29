"""CGEventTap capture backend — CA-grade timing for macOS.

Why this exists: pynput timestamps events at the Python callback, which admits
scheduler/GIL jitter at the millisecond scale that keystroke dwell/latency
features are most sensitive to (Killourhy & Maxion, IEEE/IFIP DSN 2009). A
listen-only CGEventTap exposes the OS event's own hardware timestamp
(CGEventGetTimestamp) and the auto-repeat flag (kCGKeyboardEventAutorepeat),
which pynput does not surface.

Timing model: on modern macOS CGEventGetTimestamp is nanoseconds since boot —
the same timebase as time.monotonic() — so `ts * 1e-9 - session_start` is the
true event time with no callback jitter. We auto-detect the unit on the first
event (nanoseconds vs legacy mach-ticks) by checking which scaling lands near
time.monotonic(), so this stays correct on older/Intel machines too.

Exposes start()/stop() so it's interchangeable with the pynput listeners.
Requires the Input Monitoring permission; if the tap can't be created,
start() raises and the caller falls back to pynput.
"""

from __future__ import annotations

import ctypes
import threading
import time
from typing import Callable

import Quartz

from .window_context import get_frontmost_window_context


# --- tick -> seconds conversion (mach timebase) ---------------------------

class _MachTimebase(ctypes.Structure):
    _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]


_NANOSECOND = 1e-9  # CGEventGetTimestamp unit on modern macOS


def mach_seconds_per_tick() -> float:
    """Seconds per mach-absolute-time tick (legacy timestamp unit)."""
    try:
        libc = ctypes.CDLL("libSystem.dylib")
        tb = _MachTimebase()
        libc.mach_timebase_info(ctypes.byref(tb))
        if tb.denom:
            return (tb.numer / tb.denom) / 1e9
    except Exception:
        pass
    return time.get_clock_info("monotonic").resolution


def detect_timestamp_scale(ts: int, mono_now: float) -> float:
    """Pick the seconds-per-unit scale so ``ts * scale`` lands on the
    time.monotonic() (since-boot) timebase. Handles both nanosecond and
    mach-tick timestamps; defaults to nanoseconds if neither aligns."""
    candidates = (_NANOSECOND, mach_seconds_per_tick())
    best = min(candidates, key=lambda s: abs(ts * s - mono_now))
    if abs(ts * best - mono_now) > 2.0:
        return _NANOSECOND
    return best


# --- US ANSI keycode -> character (for the alnum labeling rule) ------------
# Only alphanumerics need a literal label; every other key becomes vk<code>,
# so this map is deliberately limited to letters and digits.
_KEYCODE_TO_CHAR = {
    0: "a", 1: "s", 2: "d", 3: "f", 4: "h", 5: "g", 6: "z", 7: "x", 8: "c",
    9: "v", 11: "b", 12: "q", 13: "w", 14: "e", 15: "r", 16: "y", 17: "t",
    31: "o", 32: "u", 34: "i", 35: "p", 37: "l", 38: "j", 40: "k", 45: "n",
    46: "m", 18: "1", 19: "2", 20: "3", 21: "4", 23: "5", 22: "6", 26: "7",
    28: "8", 25: "9", 29: "0",
}


def build_key_label(keycode: int) -> str:
    char = _KEYCODE_TO_CHAR.get(keycode)
    label = char if char is not None else f"vk{keycode}"
    return f"SimKey:{label};{keycode}"


def _button_name(event, event_type: int) -> str:
    if event_type in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        return "Button.left"
    if event_type in (Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp):
        return "Button.right"
    n = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventButtonNumber)
    return "Button.middle" if n == 2 else f"Button.x{n}"


class CGEventTapListener:
    def __init__(self, signal_type: str, start_monotonic: float,
                 callback: Callable[[list], None]) -> None:
        self._signal = signal_type
        self._start = start_monotonic
        self._callback = callback
        self._scale: float | None = None   # detected on first event
        self._down_mods: set[int] = set()

        self._tap = None
        self._source = None
        self._runloop = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._ready = threading.Event()
        self._create_ok = False

    # -- lifecycle --
    def start(self) -> None:
        self._thread.start()
        self._ready.wait(timeout=2.0)
        if not self._create_ok:
            raise RuntimeError("CGEventTapCreate failed (Input Monitoring "
                               "permission or no window session?)")

    def stop(self) -> None:
        if self._tap is not None:
            Quartz.CGEventTapEnable(self._tap, False)
        if self._runloop is not None:
            Quartz.CFRunLoopStop(self._runloop)
        self._thread.join(timeout=1.0)

    # -- internals --
    def _event_mask(self) -> int:
        if self._signal == "keyboard":
            types = (Quartz.kCGEventKeyDown, Quartz.kCGEventKeyUp,
                     Quartz.kCGEventFlagsChanged)
        else:
            types = (Quartz.kCGEventMouseMoved,
                     Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp,
                     Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp,
                     Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp,
                     Quartz.kCGEventLeftMouseDragged,
                     Quartz.kCGEventRightMouseDragged,
                     Quartz.kCGEventOtherMouseDragged,
                     Quartz.kCGEventScrollWheel)
        mask = 0
        for t in types:
            mask |= (1 << t)
        return mask

    def _run(self) -> None:
        try:
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                self._event_mask(),
                self._on_event,
                None)
        except Exception:
            tap = None
        if not tap:
            self._create_ok = False
            self._ready.set()
            return

        self._tap = tap
        self._source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        self._runloop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(self._runloop, self._source,
                                  Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)
        self._create_ok = True
        self._ready.set()
        Quartz.CFRunLoopRun()

    def _elapsed(self, ts: int) -> float:
        # Spurious events (e.g. tap re-enable) can carry timestamp 0; fall back
        # to the callback clock for those rather than emit a negative offset.
        if ts <= 0:
            return time.monotonic() - self._start
        if self._scale is None:
            self._scale = detect_timestamp_scale(ts, time.monotonic())
        # ts * scale is on the monotonic (since-boot) timebase, so subtracting
        # the session's monotonic start gives the true event-time offset.
        return ts * self._scale - self._start

    def _on_event(self, proxy, event_type, event, refcon):
        # If the OS disables the tap (timeout/user input overflow), re-enable.
        if event_type in (Quartz.kCGEventTapDisabledByTimeout,
                          Quartz.kCGEventTapDisabledByUserInput):
            if self._tap is not None:
                Quartz.CGEventTapEnable(self._tap, True)
            return event

        ts = Quartz.CGEventGetTimestamp(event)
        elapsed = self._elapsed(ts)
        window = get_frontmost_window_context()

        try:
            if self._signal == "keyboard":
                self._handle_key(event_type, event, elapsed, window)
            else:
                self._handle_mouse(event_type, event, elapsed, window)
        except Exception:
            pass
        return event

    def _handle_key(self, event_type, event, elapsed, window) -> None:
        keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode)
        label = build_key_label(keycode)

        if event_type == Quartz.kCGEventKeyDown:
            autorepeat = bool(Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventAutorepeat))
            self._callback(["press", label, elapsed, window,
                            {"autorepeat": autorepeat}])
        elif event_type == Quartz.kCGEventKeyUp:
            self._callback(["release", label, elapsed, window,
                            {"autorepeat": False}])
        elif event_type == Quartz.kCGEventFlagsChanged:
            # Modifiers don't emit key down/up; infer from tracked state.
            if keycode in self._down_mods:
                self._down_mods.discard(keycode)
                action = "release"
            else:
                self._down_mods.add(keycode)
                action = "press"
            self._callback([action, label, elapsed, window,
                            {"autorepeat": False}])

    def _handle_mouse(self, event_type, event, elapsed, window) -> None:
        loc = Quartz.CGEventGetLocation(event)
        x, y = float(loc.x), float(loc.y)

        if event_type in (Quartz.kCGEventMouseMoved,
                          Quartz.kCGEventLeftMouseDragged,
                          Quartz.kCGEventRightMouseDragged,
                          Quartz.kCGEventOtherMouseDragged):
            self._callback(["move", [x, y], elapsed, window])
        elif event_type in (Quartz.kCGEventLeftMouseDown,
                            Quartz.kCGEventRightMouseDown,
                            Quartz.kCGEventOtherMouseDown):
            self._callback(["click", [x, y, _button_name(event, event_type)],
                            elapsed, window])
        elif event_type in (Quartz.kCGEventLeftMouseUp,
                            Quartz.kCGEventRightMouseUp,
                            Quartz.kCGEventOtherMouseUp):
            self._callback(["release", [x, y, _button_name(event, event_type)],
                            elapsed, window])
        elif event_type == Quartz.kCGEventScrollWheel:
            dy = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGScrollWheelEventDeltaAxis1)
            dx = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGScrollWheelEventDeltaAxis2)
            self._callback(["scroll", [x, y, dx, dy], elapsed, window])
