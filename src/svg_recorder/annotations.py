"""Timed captions: parse an --annotate file and add its footer to an SVG."""

from __future__ import annotations

import re
import textwrap
from html import escape
from pathlib import Path

from .svgwriter import BASELINE, fmt

CELL = (8, 17)  # the cell size svg_recorder draws with

Note = tuple[float, str]  # (seconds from the start, text shown from then on)


class AnnotationError(ValueError):
    """A line of the annotation file that cannot be read."""

    def __init__(self, line_no: int, reason: str):
        super().__init__(f"line {line_no}: {reason}")
        self.line_no = line_no


class SvgError(ValueError):
    """An SVG that an annotation footer cannot be added to."""


_TIME = re.compile(r"(?:(\d+):)?(\d+(?:\.\d*)?)$")


def parse_time(text: str) -> float | None:
    """Seconds for 'M:S', 'M:S.F' or plain 'S' / 'S.F'; None if text is not a time."""
    m = _TIME.match(text)
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + float(m.group(2))


def parse_annotations(text: str) -> list[Note]:
    """The notes of an annotation file, in time order.

    Each line is a time offset followed by the text to show from that time
    until the next note; a time with no text blanks the footer.  Blank lines
    and lines starting with '#' are skipped.
    """
    notes: list[Note] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        stamp, _, rest = line.replace("\t", " ").partition(" ")
        t = parse_time(stamp)
        if t is None:
            raise AnnotationError(line_no, f"expected a time such as 1:03 or 2:59.5, not {stamp!r}")
        notes.append((t, rest.strip()))
    notes.sort(key=lambda note: note[0])  # stable: of two notes at one time the later line wins
    return notes


def load_annotations(path: str | Path) -> list[Note]:
    return parse_annotations(Path(path).read_text(encoding="utf-8"))


_SVG_TAG = re.compile(r"<svg\b[^>]*>")
_LOOP = re.compile(r"animation:[an]\d+ ([\d.]+)s steps\(1,end\) infinite")
_NOTE_CLASS = re.compile(r"\.n(\d+)\{")


def loop_duration(svg: str) -> float | None:
    """The length of a looping animation in seconds, or None if it plays once."""
    m = _LOOP.search(svg)
    return float(m.group(1)) if m else None


def _number_attr(tag: str, name: str) -> float:
    m = re.search(rf'\s{name}="([\d.]+)"', tag)
    if not m:
        raise SvgError(f"the <svg> element has no numeric {name}")
    return float(m.group(1))


def annotate_svg(svg: str, notes: list[Note], colors: tuple[str, str] = ("#303030", "#f0f0f0"),
                 cell: tuple[int, int] = CELL) -> str:
    """A copy of `svg` with a footer below it that shows each note from its time on.

    The footer is as many rows tall as the longest note needs once wrapped to
    the width of the SVG.  In a looping SVG a note at or past the loop's end
    would never be seen and is left out.
    """
    tag_match = _SVG_TAG.search(svg)
    end = svg.rfind("</svg>")
    if not tag_match or end < 0:
        raise SvgError("no <svg> element found")
    tag = tag_match.group(0)
    width, height = _number_attr(tag, "width"), _number_attr(tag, "height")
    if not re.search(r'\sviewBox="[^"]*"', tag):
        raise SvgError("the <svg> element has no viewBox")

    cw, ch = cell
    cols = max(1, int(width) // cw)
    duration = loop_duration(svg)
    if duration is not None:
        notes = [n for n in notes if n[0] < duration]
    wrapped = [(t, textwrap.wrap(text, cols)) for t, text in notes]
    rows = max([len(lines) for _, lines in wrapped] + [1])
    foot_h = rows * ch
    bg, fg = (escape(c, quote=True) for c in colors)
    back = f'<rect x="0" y="{fmt(height)}" width="{fmt(width)}" height="{foot_h}" style="fill:{bg}"/>'

    css: list[str] = []
    parts = [back]
    serial = max([int(n) for n in _NOTE_CLASS.findall(svg)] + [0])
    for t, lines in wrapped:
        body = back + "".join(
            f'<text x="0" y="{fmt(height + i * ch + BASELINE)}" textLength="{len(line) * cw}" '
            f'style="fill:{fg}">{escape(line, quote=False)}</text>'
            for i, line in enumerate(lines))
        if t <= 0:
            parts.append(body)
            continue
        serial += 1
        name = f"n{serial}"
        if duration is not None:
            css.append(f".{name}{{animation:{name} {fmt(duration)}s steps(1,end) infinite}}"
                       f"@keyframes {name}{{0%{{visibility:hidden}}"
                       f"{fmt(100.0 * t / duration)}%{{visibility:visible}}}}")
        else:
            css.append(f".{name}{{visibility:hidden;animation:{name} 1ms steps(1,start) {fmt(t)}s forwards}}"
                       f"@keyframes {name}{{to{{visibility:visible}}}}")
        parts.append(f'<g class="{name}">{body}</g>')

    new_height = fmt(height + foot_h)
    new_tag = re.sub(r'(\sheight=")[\d.]+(")', rf"\g<1>{new_height}\g<2>", tag, count=1)
    new_tag = re.sub(r'(\sviewBox=")[^"]*(")', rf"\g<1>0 0 {fmt(width)} {new_height}\g<2>", new_tag, count=1)
    if "</style>" in svg[tag_match.end():end]:
        head, _, body = svg[tag_match.end():end].partition("</style>")
        inner = head + "".join(css) + "</style>" + body
    else:
        inner = (f"<style>{''.join(css)}</style>" if css else "") + svg[tag_match.end():end]
    return svg[:tag_match.start()] + new_tag + inner + "".join(parts) + svg[end:]
