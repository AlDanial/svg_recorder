"""Read and write asciicast v2 files, the recording intermediate format."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .palette import KITTY_DEFAULT, Palette

Event = tuple[float, str, bytes]

_ENC = "surrogateescape"


@dataclass(frozen=True)
class Header:
    width: int
    height: int
    timestamp: int
    palette: Palette
    cell: tuple[int, int] = (8, 17)

    def to_json(self) -> str:
        return json.dumps({
            "version": 2,
            "width": self.width,
            "height": self.height,
            "timestamp": self.timestamp,
            "theme": self.palette.to_theme(),
            "cell": list(self.cell),
        })

    @classmethod
    def from_json(cls, line: str) -> "Header":
        d = json.loads(line)
        palette = Palette.from_theme(d["theme"]) if "theme" in d else KITTY_DEFAULT
        cell = d.get("cell", [8, 17])
        return cls(int(d["width"]), int(d["height"]), int(d.get("timestamp", 0)),
                   palette, (int(cell[0]), int(cell[1])))


class Writer:
    def __init__(self, path: str | Path, header: Header):
        self._f = open(path, "w", encoding="utf-8")
        self._f.write(header.to_json() + "\n")

    def write(self, t: float, kind: str, data: bytes) -> None:
        line = json.dumps([round(t, 6), kind, data.decode("utf-8", _ENC)])
        self._f.write(line + "\n")

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> "Writer":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def read(path: str | Path) -> tuple[Header, list[Event]]:
    with open(path, encoding="utf-8") as f:
        header = Header.from_json(f.readline())
        events: list[Event] = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            t, kind, data = json.loads(line)
            events.append((float(t), kind, data.encode("utf-8", _ENC)))
    return header, events
