"""Parse the --annotation file: mode regexes and per-mode keystroke descriptions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


class AnnotationError(ValueError):
    def __init__(self, line_no: int, reason: str):
        super().__init__(f"line {line_no}: {reason}")
        self.line_no = line_no


@dataclass
class Annotations:
    modes: list[tuple[str, re.Pattern]] = field(default_factory=list)
    entries: dict[tuple[str, str], str] = field(default_factory=dict)

    def detect_mode(self, rows: Iterable[str]) -> str | None:
        rows = list(rows)
        for name, pattern in self.modes:
            for row in rows:
                if pattern.search(row):
                    return name
        return None

    def describe(self, mode: str | None, key: str | None) -> str:
        if mode is None or key is None:
            return ""
        return self.entries.get((mode, key), "")


def parse_annotations(text: str) -> Annotations:
    result = Annotations()
    pending: list[tuple[int, str, str, str]] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=2)
        if parts[0] == "mode":
            if len(parts) < 3:
                raise AnnotationError(line_no, "mode line needs a name and a regex")
            try:
                pattern = re.compile(parts[2])
            except re.error as e:
                raise AnnotationError(line_no, f"bad regex: {e}") from None
            result.modes.append((parts[1], pattern))
            continue
        if len(parts) < 3:
            raise AnnotationError(line_no, "expected: <mode> <key> <description>")
        pending.append((line_no, parts[0], parts[1], parts[2]))
    declared = {name for name, _ in result.modes}
    for line_no, mode, key, desc in pending:
        if mode not in declared:
            raise AnnotationError(line_no, f"mode '{mode}' has no mode line")
        result.entries[(mode, key)] = desc
    return result


def load_annotations(path: str | Path) -> Annotations:
    return parse_annotations(Path(path).read_text(encoding="utf-8"))
