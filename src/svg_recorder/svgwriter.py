"""Emit patches as a self-contained animated SVG."""

from __future__ import annotations

import re
from collections import Counter

from .palette import ANSI_NAMES, Palette
from .patches import Cell, Patch

FONT_FAMILY = "DejaVu Sans Mono,Menlo,Consolas,monospace"
FONT_SIZE = 14
BASELINE = 13

_DIM_NAMES = set(ANSI_NAMES[:8]) | {"brown"}


def fmt(x: float) -> str:
    s = f"{x:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _Classes:
    """Assigns short class names to colors in first-seen order."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        self.names: dict[str, str] = {}

    def get(self, value: str) -> str:
        if value not in self.names:
            self.names[value] = f"{self.prefix}{len(self.names)}"
        return self.names[value]

    def css(self) -> str:
        return "".join(f".{name}{{fill:{value}}}" for value, name in self.names.items())


class SvgWriter:
    def __init__(self, palette: Palette, cols: int, rows: int, cell: tuple[int, int] = (8, 17),
                 loop: bool = True, hold: float = 2.0, dedup: bool = True):
        self.palette = palette
        self.cols, self.rows = cols, rows
        self.cw, self.ch = cell
        self.loop, self.hold, self.dedup = loop, hold, dedup
        self._fg = _Classes("f")
        self._bg = _Classes("g")
        self._frames: list[tuple[float, list[Patch]]] = []

    def add_frame(self, t: float, patches: list[Patch]) -> None:
        if patches:
            self._frames.append((t, list(patches)))

    # ----- per-cell style -------------------------------------------------

    def _colors(self, c: Cell) -> tuple[str, str]:
        """Effective (fg, bg) as '#rrggbb' after bold-brightening and reverse."""
        fg_name = c.fg
        if c.bold and fg_name in _DIM_NAMES:
            index = 3 if fg_name == "brown" else ANSI_NAMES.index(fg_name)
            fg_name = ANSI_NAMES[index + 8]
        fg = self.palette.resolve(fg_name, self.palette.fg)
        bg = self.palette.resolve(c.bg, self.palette.bg)
        return (bg, fg) if c.reverse else (fg, bg)

    def _text_class(self, c: Cell, fg: str) -> str:
        parts = []
        if fg != self.palette.fg:
            parts.append(self._fg.get(fg))
        if c.bold:
            parts.append("b")
        if c.italic:
            parts.append("i")
        if c.underline:
            parts.append("u")
        return " ".join(parts)

    # ----- patch body -----------------------------------------------------

    def _body(self, p: Patch, ox: int, oy: int) -> str:
        """Markup for a patch with its top-left corner at pixel (ox, oy)."""
        cw, ch = self.cw, self.ch
        width_px = p.width * cw
        out = []
        if p.erase:
            out.append(f'<rect x="{ox}" y="{oy}" width="{width_px}" height="{p.height * ch}" class="e"/>')
        # background runs
        for ri, row in enumerate(p.rows):
            styles = [self._colors(c) for c in row]
            i = 0
            while i < len(row):
                bg = styles[i][1]
                j = i
                while j < len(row) and styles[j][1] == bg:
                    j += 1
                if bg != self.palette.bg:
                    out.append(f'<rect x="{ox + i * cw}" y="{oy + ri * ch}" width="{(j - i) * cw}" '
                               f'height="{ch}" class="{self._bg.get(bg)}"/>')
                i = j
        # text runs per row: list of (class, text, cell_count) -- cell_count counts
        # continuation cells (char == "") so textLength always spans the run's cells.
        row_markup: list[list[tuple[str, str, int]]] = []
        for row in p.rows:
            runs: list[list] = []
            for c in row:
                fg, _ = self._colors(c)
                cls = self._text_class(c, fg)
                if runs and runs[-1][0] == cls:
                    runs[-1][1] += c.char
                    runs[-1][2] += 1
                else:
                    runs.append([cls, c.char, 1])
            row_markup.append([tuple(run) for run in runs])
        if len(p.rows) == 1 and len(row_markup[0]) == 1:
            cls, text, _ncells = row_markup[0][0]
            if not text:
                return "".join(out)
            attr = f' class="{cls}"' if cls else ""
            out.append(f'<text x="{ox}" y="{oy + BASELINE}" textLength="{width_px}"{attr}>{_esc(text)}</text>')
            return "".join(out)
        # A run of wide-character continuation cells carries no text; an empty
        # tspan would not apply its x, so drop it and shift the next run that
        # does carry text by the cells it stood for.
        emitted: list[list[tuple[int | None, str, str, int]]] = []
        for runs in row_markup:
            col, shifted, kept = 0, False, []
            for cls, text, ncells in runs:
                if text:
                    kept.append((col if shifted else None, cls, text, ncells))
                    shifted = False
                else:
                    shifted = True
                col += ncells
            emitted.append(kept)
        if not any(emitted):
            return "".join(out)
        text_x = ox
        if emitted[0] and emitted[0][0][0]:
            xcol, cls, text, ncells = emitted[0][0]
            text_x = ox + xcol * cw
            emitted[0][0] = (None, cls, text, ncells)
        parts = [f'<text x="{text_x}" y="{oy + BASELINE}">']
        for ri, runs in enumerate(emitted):
            for k, (xcol, cls, text, ncells) in enumerate(runs):
                attrs = ""
                if k == 0 and ri > 0:
                    attrs += f' x="{ox + (xcol or 0) * cw}" y="{oy + ri * ch + BASELINE}"'
                elif xcol is not None:
                    attrs += f' x="{ox + xcol * cw}"'
                attrs += f' textLength="{ncells * cw}"'
                if cls:
                    attrs += f' class="{cls}"'
                parts.append(f"<tspan{attrs}>{_esc(text)}</tspan>")
        parts.append("</text>")
        out.append("".join(parts))
        return "".join(out)

    # ----- document -------------------------------------------------------

    def to_string(self, duration: float | None = None) -> str:
        cw, ch = self.cw, self.ch
        last_t = self._frames[-1][0] if self._frames else 0.0
        if duration is None:
            duration = last_t + self.hold
        duration = max(duration, last_t, 0.001)
        times: dict[float, str] = {}

        def time_class(t: float) -> str:
            if t <= 0:
                return ""
            key = round(t, 3)
            if key not in times:
                times[key] = f"t{len(times) + 1}"
            return times[key]

        # First pass: count bodies for dedup (bodies at origin are position independent).
        counts: Counter[str] = Counter()
        keyed: list[tuple[float, Patch, str]] = []
        for t, patches in self._frames:
            for p in patches:
                key = self._body(p, 0, 0)
                if not key:  # nothing to draw: continuation cells only, no erase
                    continue
                counts[key] += 1
                keyed.append((t, p, key))
        defs_ids: dict[str, str] = {}
        if self.dedup:
            for key, n in counts.items():
                if n >= 2:
                    defs_ids[key] = f"p{len(defs_ids)}"

        elements = []
        for t, p, key in keyed:
            cls = time_class(t)
            x, y = p.col * cw, p.row * ch
            if key in defs_ids:
                attr = f' class="{cls}"' if cls else ""
                elements.append(f'<use href="#{defs_ids[key]}" x="{x}" y="{y}"{attr}/>')
            else:
                body = self._body(p, x, y)
                elements.append(f'<g class="{cls}">{body}</g>' if cls else body)

        style = [
            f"text{{font-family:{FONT_FAMILY};font-size:{FONT_SIZE}px;fill:{self.palette.fg};white-space:pre}}",
            ".b{font-weight:bold}.i{font-style:italic}.u{text-decoration:underline}",
            f".e{{fill:{self.palette.bg}}}",
            self._fg.css(), self._bg.css(),
        ]
        if times:
            if self.loop:
                for key, name in times.items():
                    pct = fmt(100.0 * key / duration)
                    style.append(f".{name}{{animation:a{name[1:]} {fmt(duration)}s steps(1,end) infinite}}"
                                 f"@keyframes a{name[1:]}{{0%{{visibility:hidden}}{pct}%{{visibility:visible}}}}")
            else:
                style.append("[class^=t]{visibility:hidden;animation:s 1ms steps(1,end) forwards}"
                             "@keyframes s{to{visibility:visible}}")
                for key, name in times.items():
                    style.append(f".{name}{{animation-delay:{fmt(key)}s}}")

        w_px, h_px = self.cols * cw, self.rows * ch
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_px}" height="{h_px}" '
            f'viewBox="0 0 {w_px} {h_px}" xml:space="preserve">',
            f"<style>{''.join(style)}</style>",
            f'<rect width="100%" height="100%" fill="{self.palette.bg}"/>',
        ]
        if defs_ids:
            parts.append("<defs>" + "".join(f'<g id="{pid}">{key}</g>' for key, pid in defs_ids.items()) + "</defs>")
        parts += elements
        parts.append("</svg>")
        return "".join(parts)


_VIOLATIONS = [
    (re.compile(r"<script", re.I), "script element"),
    (re.compile(r"@import", re.I), "@import in style"),
    (re.compile(r"url\(", re.I), "url( reference"),
    (re.compile(r"@font-face", re.I), "@font-face"),
    (re.compile(r"""(?:xlink:)?href=["'](?!#)""", re.I), "href to non-local target"),
]


def check_self_contained(svg: str) -> list[str]:
    return [label for pattern, label in _VIOLATIONS if pattern.search(svg)]
