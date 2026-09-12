"""Read and write asciicast v2 files, the recording intermediate format."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .palette import KITTY_DEFAULT, Palette

Event = tuple[float, str, bytes]

_ENC = "surrogateescape"


class CastError(ValueError):
    """A recording file that is not readable as asciicast v2."""


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
    def from_json(cls, line: str, where: str = "line 1") -> "Header":
        try:
            d = json.loads(line)
        except ValueError as e:
            raise CastError(f"{where}: header is not JSON: {e}") from None
        if not isinstance(d, dict):
            raise CastError(f"{where}: header is not a JSON object")
        try:
            width, height = int(d["width"]), int(d["height"])
        except (KeyError, TypeError, ValueError):
            raise CastError(f"{where}: header needs numeric 'width' and 'height'") from None
        try:
            palette = Palette.from_theme(d["theme"]) if "theme" in d else KITTY_DEFAULT
            cell = d.get("cell", [8, 17])
            return cls(width, height, int(d.get("timestamp", 0)), palette,
                       (int(cell[0]), int(cell[1])))
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise CastError(f"{where}: bad header field: {e}") from None


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
    """Parse an asciicast v2 file, raising CastError on anything malformed."""
    name = Path(path).name
    with open(path, encoding="utf-8") as f:
        header = Header.from_json(f.readline(), f"{name} line 1")
        events: list[Event] = []
        for lineno, line in enumerate(f, start=2):
            line = line.strip()
            if not line:
                continue
            where = f"{name} line {lineno}"
            try:
                event = json.loads(line)
            except ValueError as e:
                raise CastError(f"{where}: event is not JSON: {e}") from None
            if (not isinstance(event, list) or len(event) != 3
                    or not isinstance(event[0], (int, float)) or isinstance(event[0], bool)
                    or not isinstance(event[1], str) or not isinstance(event[2], str)):
                raise CastError(f"{where}: event is not a [time, \"o\"|\"i\", data] list")
            t, kind, data = event
            events.append((float(t), kind, data.encode("utf-8", _ENC)))
    return header, events
