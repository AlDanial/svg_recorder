"""Wrap an animated SVG in a self-contained HTML page with playback controls."""

from __future__ import annotations

from html import escape
from importlib.resources import files

SVG_MARKER = "<!-- The SVG content goes here -->"
TITLE_MARKER = "%TITLE%"


def wrap_svg(svg: str, title: str) -> str:
    """The player page with `svg` inlined and `title` as its name."""
    template = files(__package__).joinpath("player.html").read_text(encoding="utf-8")
    # Fill the title into the two halves before the SVG joins them, so text in
    # the recording that happens to look like a marker is never rescanned.
    head, tail = template.split(SVG_MARKER)
    name = escape(title, quote=True)
    return head.replace(TITLE_MARKER, name) + svg + tail.replace(TITLE_MARKER, name)
