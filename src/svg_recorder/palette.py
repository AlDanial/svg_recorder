"""Terminal color palette: defaults, OSC queries, and pyte color resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass

ANSI_NAMES = [
    "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "brightblack", "brightred", "brightgreen", "brightyellow",
    "brightblue", "brightmagenta", "brightcyan", "brightwhite",
]
_INDEX = {name: i for i, name in enumerate(ANSI_NAMES)}
_INDEX["brown"] = 3  # pyte's name for SGR 33
_INDEX["brightbrown"] = 11  # pyte's name for SGR 93
_INDEX["bfightmagenta"] = 13  # pyte's (misspelled) name for SGR 95

_HEX6 = re.compile(r"[0-9a-fA-F]{6}")
# A CSS color that is not a bare 6-digit hex: a function such as rgb(1,2,3) or
# a keyword such as navy. Anything matching is passed through untouched.
_CSS_FUNCTION = re.compile(r"[A-Za-z-]+\([^()]*\)")
_CSS_KEYWORD = re.compile(r"[A-Za-z]+")
_OSC_REPLY = re.compile(
    rb"\x1b\](10|11|4;(\d+));rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)(?:\x1b\\|\x07)"
)


@dataclass(frozen=True)
class Palette:
    fg: str
    bg: str
    colors: tuple[str, ...]

    def resolve(self, color: str, default: str) -> str:
        """Map a pyte color value to a CSS color.

        pyte names and bare 6-digit hex become '#rrggbb' from this palette.
        Anything else that is already a CSS color -- '#333', 'navy',
        'rgb(1,2,3)' -- is passed through verbatim, so --footer-colors accepts
        any CSS color value.
        """
        if color == "default":
            return default
        if color in _INDEX:
            return self.colors[_INDEX[color]]
        if color.startswith("#"):
            return color.lower()
        if _HEX6.fullmatch(color):
            return "#" + color.lower()
        if _CSS_FUNCTION.fullmatch(color) or _CSS_KEYWORD.fullmatch(color):
            return color
        return default

    def to_theme(self) -> dict:
        return {"fg": self.fg, "bg": self.bg, "palette": ":".join(self.colors)}

    @classmethod
    def from_theme(cls, d: dict) -> "Palette":
        return cls(d["fg"], d["bg"], tuple(d["palette"].split(":")))


KITTY_DEFAULT = Palette(
    fg="#dddddd",
    bg="#000000",
    colors=(
        "#000000", "#cc0403", "#19cb00", "#cecb00",
        "#0d73cc", "#cb1ed1", "#0dcdcd", "#dddddd",
        "#767676", "#f2201f", "#23fd00", "#fffd00",
        "#1a8fff", "#fd28ff", "#14ffff", "#ffffff",
    ),
)

OSC_QUERY = (
    b"\x1b]10;?\x1b\\" + b"\x1b]11;?\x1b\\"
    + b"".join(b"\x1b]4;%d;?\x1b\\" % i for i in range(16))
)


def _component(h: bytes) -> str:
    """Take the two most significant hex digits of a 1..4 digit component."""
    s = h.decode("ascii").lower()
    if len(s) == 1:
        s = s * 2
    return s[:2]


def apply_osc_replies(data: bytes, base: Palette) -> Palette:
    """Return a copy of base updated with any OSC 10/11/4 replies found in data."""
    fg, bg, colors = base.fg, base.bg, list(base.colors)
    for m in _OSC_REPLY.finditer(data):
        value = "#" + _component(m.group(3)) + _component(m.group(4)) + _component(m.group(5))
        kind = m.group(1)
        if kind == b"10":
            fg = value
        elif kind == b"11":
            bg = value
        else:
            index = int(m.group(2))
            if 0 <= index < 16:
                colors[index] = value
    return Palette(fg, bg, tuple(colors))
