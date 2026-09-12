"""Recorder interface and platform selection."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol

from .asciicast import Header


class RecordError(RuntimeError):
    pass


class Recorder(Protocol):
    def record(self, command: str | None, pre_commands: list[str], cast_path: Path) -> Header:
        """Record a session to cast_path and return its header."""


def get_recorder() -> Recorder:
    if sys.platform == "win32":
        raise RecordError("recording is not supported on this platform")
    from .recorder_posix import PosixRecorder
    return PosixRecorder()
