"""Cell-level frame diffing into rectangular patches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple


class Cell(NamedTuple):
    char: str
    fg: str
    bg: str
    bold: bool
    italic: bool
    underline: bool
    reverse: bool


BLANK = Cell(" ", "default", "default", False, False, False, False)

Frame = list[list[Cell]]


def blank_frame(cols: int, rows: int) -> Frame:
    return [[BLANK] * cols for _ in range(rows)]


def is_blank(cell: Cell) -> bool:
    return cell.char in (" ", "") and cell.bg == "default" and not cell.reverse


@dataclass(frozen=True)
class Patch:
    col: int
    row: int
    width: int
    rows: tuple[tuple[Cell, ...], ...]
    erase: bool

    @property
    def height(self) -> int:
        return len(self.rows)


def row_runs(old_row: list[Cell], new_row: list[Cell], gap: int) -> list[tuple[int, int]]:
    """Half-open column ranges of changed cells, merging gaps of at most `gap` cells."""
    runs: list[tuple[int, int]] = []
    start = end = -1
    for i, (a, b) in enumerate(zip(old_row, new_row)):
        if a == b:
            continue
        if start >= 0 and i - end <= gap:
            end = i + 1
        else:
            if start >= 0:
                runs.append((start, end))
            start, end = i, i + 1
    if start >= 0:
        runs.append((start, end))
    return runs


def _make_patch(old: Frame, new: Frame, col: int, row: int, width: int, height: int) -> Patch:
    rows = tuple(tuple(new[r][col:col + width]) for r in range(row, row + height))
    erase = any(not is_blank(c) for r in range(row, row + height) for c in old[r][col:col + width])
    return Patch(col, row, width, rows, erase)


def diff_frames(old: Frame, new: Frame, gap: int = 2, full_threshold: float = 0.5) -> list[Patch]:
    height = len(new)
    cols = len(new[0]) if height else 0
    runs_by_row: dict[int, list[tuple[int, int]]] = {}
    changed = 0
    for r in range(height):
        if old[r] is new[r]:
            continue
        runs = row_runs(old[r], new[r], gap)
        if runs:
            runs_by_row[r] = runs
            changed += sum(e - s for s, e in runs)
    if not runs_by_row:
        return []
    if cols * height and changed / (cols * height) > full_threshold:
        return [_make_patch(old, new, 0, 0, cols, height)]

    patches: list[Patch] = []
    open_patches: dict[tuple[int, int], tuple[int, int]] = {}  # (start, end) -> (first_row, n_rows)
    for r in range(height):
        runs = runs_by_row.get(r, [])
        next_open: dict[tuple[int, int], tuple[int, int]] = {}
        for run in runs:
            if run in open_patches:
                first, n = open_patches.pop(run)
                next_open[run] = (first, n + 1)
            else:
                next_open[run] = (r, 1)
        for (s, e), (first, n) in open_patches.items():
            patches.append(_make_patch(old, new, s, first, e - s, n))
        open_patches = next_open
    for (s, e), (first, n) in open_patches.items():
        patches.append(_make_patch(old, new, s, first, e - s, n))
    patches.sort(key=lambda p: (p.row, p.col))
    return patches
