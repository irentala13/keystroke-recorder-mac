"""input_recorder — macOS keystroke/mouse recorder.

A macOS-native (Python + pynput) counterpart to the Windows-only
``keystroke-recorder-win`` C++ tool. Records low-level keyboard or mouse input
and writes it to JSON files with a schema adapted from — but structurally
parallel to — the Windows recorder, for the same behavioral-biometrics test
pipeline.
"""

__version__ = "1.0.0"
