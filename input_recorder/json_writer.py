"""RecordingWriter — buffers payload entries and flushes JSON files.

Structurally parallel to json_writer.cpp: same entity/metadata/payload layout,
same KBD_JSON / MOUSE_JSON subdirectories, same <username><N>.json filenames,
compact (whitespace-free) JSON. Keys are emitted in the alphabetical order the
reference recordings use.
"""

from __future__ import annotations

import json
import os
import threading
import time

from .displays import MonitorInfo
from .entity_info import EntityInfo


class RecordingWriter:
    def __init__(self, output_dir: str, signal_type: str, entity: EntityInfo,
                 file_write_interval_seconds: int,
                 monitor_info: list[MonitorInfo] | None = None) -> None:
        self._output_dir = output_dir
        self._signal_type = signal_type
        self._entity = entity
        self._file_write_interval = file_write_interval_seconds
        self._monitor_info = monitor_info or []
        self._payload: list = []
        self._lock = threading.Lock()
        self._sequence = 0
        self.total_events = 0    # cumulative across the whole session
        self.files_written = 0

    def _subdirectory_name(self) -> str:
        return "MOUSE_JSON" if self._signal_type == "mouse" else "KBD_JSON"

    @property
    def output_subdir(self) -> str:
        return os.path.join(self._output_dir, self._subdirectory_name())

    def add_payload_entry(self, entry: list) -> None:
        # Called from the pynput listener thread; the main thread flushes.
        with self._lock:
            self._payload.append(entry)
            self.total_events += 1

    def flush(self, username_prefix: str) -> tuple[str, int] | None:
        """Write buffered events to the next file. Returns (path, count) on a
        write, or None if there was nothing to write / the write failed."""
        with self._lock:
            if not self._payload:
                return None
            payload = self._payload
            self._payload = []
            self._sequence += 1
            sequence = self._sequence

        entity = {
            "machine_id": self._entity.machine_id,
            "machine_name": self._entity.machine_name,
            "tenant": self._entity.tenant,
            "tuid": self._entity.tuid,
            "user_id": self._entity.user_id,
        }

        metadata: dict = {"file_write_interval": self._file_write_interval}
        if self._monitor_info:
            metadata["monitor_info"] = [
                {
                    "height": m.height,
                    "height_mm": None,
                    "is_primary": m.is_primary,
                    "name": None,
                    "width": m.width,
                    "width_mm": None,
                    "x": m.x,
                    "y": m.y,
                }
                for m in self._monitor_info
            ]
        metadata["number_of_actions"] = len(payload)
        metadata["signal_type"] = self._signal_type
        metadata["timestamp"] = time.time()
        metadata["version"] = "1"

        document = {"entity": entity, "metadata": metadata, "payload": payload}

        subdir = os.path.join(self._output_dir, self._subdirectory_name())
        try:
            os.makedirs(subdir, exist_ok=True)
        except OSError as exc:
            print(f"ERROR: could not create directory '{subdir}' ({exc})")
            return None

        filename = os.path.join(subdir, f"{username_prefix}{sequence}.json")
        try:
            with open(filename, "w", encoding="utf-8") as fh:
                json.dump(document, fh, separators=(",", ":"), ensure_ascii=False)
        except OSError as exc:
            print(f"ERROR: could not open '{filename}' for writing ({exc})")
            return None

        self.files_written += 1
        return (filename, len(payload))
