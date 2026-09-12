"""Replay a recording through pyte at fixed ticks and add footer rows."""

from __future__ import annotations

from typing import Iterator

import pyte

from .annotations import Annotations
from .asciicast import Event, Header
from .keys import KeyDecoder
from .patches import BLANK, Cell, Frame

FOOTER_KEYS = 5
BOLD_SECONDS = 2.0


class Footer:
    def __init__(self, width: int, colors: tuple[str, str], annotations: Annotations | None = None):
        self.width = width
        self.bg, self.fg = colors
        self.annotations = annotations
        self._keys: list[str] = []
        self._last_t: float | None = None

    @property
    def height(self) -> int:
        return 2 if self.annotations else 1

    def push_key(self, t: float, name: str) -> None:
        self._keys = (self._keys + [name])[-FOOTER_KEYS:]
        self._last_t = t

    def pending_until(self) -> float | None:
        """When the newest key stops being bold, or None if nothing is bold."""
        if not self._keys or self._last_t is None:
            return None
        return self._last_t + BOLD_SECONDS

    def _line(self, text: str, bold_from: int = -1) -> list[Cell]:
        cells = []
        for i, ch in enumerate(text[:self.width].ljust(self.width)):
            bold = 0 <= bold_from <= i < len(text)
            cells.append(Cell(ch, self.fg, self.bg, bold, False, False, False))
        return cells

    def rows(self, t: float, screen_rows: list[str]) -> list[list[Cell]]:
        bold_from = -1
        line = ""
        if self._keys:
            line = " ".join(self._keys)
            if self._last_t is not None and t - self._last_t < BOLD_SECONDS:
                bold_from = len(line) - len(self._keys[-1])
        out = [self._line(line, bold_from)]
        if self.annotations:
            mode = self.annotations.detect_mode(screen_rows)
            key = self._keys[-1] if self._keys else None
            out.append(self._line(self.annotations.describe(mode, key)))
        return out


class Sampler:
    def __init__(self, header: Header, events: list[Event], time_delta: float = 0.05,
                 footer: Footer | None = None, cursor: bool = False):
        self.header = header
        self.events = events
        self.time_delta = time_delta
        self.footer = footer
        self.cursor = cursor

    @property
    def end_time(self) -> float:
        return self.events[-1][0] if self.events else 0.0

    def _convert_row(self, screen: pyte.Screen, r: int) -> list[Cell]:
        line = screen.buffer[r]
        return [Cell(c.data, c.fg, c.bg, c.bold, c.italics, c.underscore, c.reverse)
                for c in (line[x] for x in range(self.header.width))]

    def frames(self) -> Iterator[tuple[float, Frame]]:
        w, h = self.header.width, self.header.height
        screen = pyte.Screen(w, h)
        stream = pyte.ByteStream(screen)
        decoder = KeyDecoder()
        rows: list[list[Cell]] = [[BLANK] * w for _ in range(h)]
        if self.footer:
            rows += self.footer.rows(0.0, [""] * h)
        prev_cursor_row: int | None = None
        idx = 0
        tick_no = 0
        drained = False
        end = self.end_time
        while True:
            t = round(tick_no * self.time_delta, 6)
            while idx < len(self.events) and self.events[idx][0] <= t:
                et, kind, data = self.events[idx]
                if kind == "o":
                    stream.feed(data)
                elif kind == "i" and self.footer:
                    for kt, name in decoder.feed(et, data):
                        self.footer.push_key(kt, name)
                idx += 1
            if not drained and idx >= len(self.events):
                # No more input is coming: a trailing bare ESC is a key too.
                drained = True
                if self.footer:
                    for kt, name in decoder.finish():
                        self.footer.push_key(kt, name)
            dirty = set(screen.dirty)
            screen.dirty.clear()
            cur_cursor_row = screen.cursor.y if self.cursor and not screen.cursor.hidden else None
            special_rows = {r for r in (prev_cursor_row, cur_cursor_row) if r is not None}
            for r in dirty:
                if 0 <= r < h and r not in special_rows:
                    rows[r] = self._convert_row(screen, r)
            for r in special_rows:
                if not (0 <= r < h):
                    continue
                candidate = self._convert_row(screen, r)
                if r == cur_cursor_row:
                    cx = screen.cursor.x
                    if cx < w:
                        candidate[cx] = candidate[cx]._replace(reverse=not candidate[cx].reverse)
                if candidate != rows[r]:
                    rows[r] = candidate
            prev_cursor_row = cur_cursor_row
            if self.footer:
                texts = ["".join(c.char for c in rows[r]) for r in range(h)]
                for i, new_row in enumerate(self.footer.rows(t, texts)):
                    if new_row != rows[h + i]:
                        rows[h + i] = new_row
            yield t, list(rows)
            stop = end
            if self.footer:
                pending = self.footer.pending_until()
                if pending is not None:
                    stop = max(stop, pending)
            if t >= stop:
                break
            tick_no += 1
