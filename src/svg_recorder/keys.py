"""Decode terminal input bytes into human readable key names."""

from __future__ import annotations

ESC_TIMEOUT = 0.05

_CSI_KEYS = {
    "A": "<UpArrow>", "B": "<DownArrow>", "C": "<RightArrow>", "D": "<LeftArrow>",
    "H": "<Home>", "F": "<End>",
    "1~": "<Home>", "2~": "<Insert>", "3~": "<Delete>", "4~": "<End>",
    "5~": "<PgUp>", "6~": "<PgDn>", "7~": "<Home>", "8~": "<End>",
    "11~": "<F1>", "12~": "<F2>", "13~": "<F3>", "14~": "<F4>", "15~": "<F5>",
    "17~": "<F6>", "18~": "<F7>", "19~": "<F8>", "20~": "<F9>", "21~": "<F10>",
    "23~": "<F11>", "24~": "<F12>",
}
_SS3_KEYS = {
    "A": "<UpArrow>", "B": "<DownArrow>", "C": "<RightArrow>", "D": "<LeftArrow>",
    "H": "<Home>", "F": "<End>", "P": "<F1>", "Q": "<F2>", "R": "<F3>", "S": "<F4>",
}
_SINGLE = {
    0x09: "<Tab>", 0x0D: "<Enter>", 0x0A: "<Enter>", 0x20: "<Space>",
    0x7F: "<Backspace>", 0x08: "<Backspace>",
}
_CTRL_PUNCT = {0x1C: "\\", 0x1D: "]", 0x1E: "^", 0x1F: "_", 0x00: "<Space>"}


def _utf8_len(lead: int) -> int:
    if lead < 0x80:
        return 1
    if 0xC2 <= lead <= 0xDF:
        return 2
    if 0xE0 <= lead <= 0xEF:
        return 3
    if 0xF0 <= lead <= 0xF4:
        return 4
    return 0  # invalid lead byte


def _modified(base: str, mods: int) -> str:
    """Prefix a key name with modifiers from an xterm modifier parameter."""
    bits = mods - 1
    prefix = ""
    if bits & 4:
        prefix += "<Ctrl>-"
    if bits & 2:
        prefix += "<Alt>-"
    if bits & 1:
        prefix += "<Shift>-"
    return prefix + base


def _parse_one(buf: bytes) -> tuple[str | None, int]:
    """Parse one key from the start of buf.

    Returns (name, consumed). name is None when buf holds an incomplete
    sequence and more bytes are needed; consumed is then 0.
    """
    b0 = buf[0]
    if b0 == 0x1B:
        if len(buf) == 1:
            return None, 0
        b1 = buf[1]
        if b1 == 0x5B:  # '['  CSI
            i = 2
            while i < len(buf) and (0x30 <= buf[i] <= 0x3F):
                i += 1
            if i >= len(buf):
                return None, 0
            if not (0x40 <= buf[i] <= 0x7E):
                return "<0x1b>", 1
            final = chr(buf[i])
            params = buf[2:i].decode("ascii")
            parts = params.split(";")
            mods = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            if final == "u" and parts[0].isdigit():  # kitty CSI u
                code = int(parts[0])
                # Check for valid Unicode code point and exclude surrogate range
                if not (0 <= code <= 0x10FFFF and not (0xD800 <= code <= 0xDFFF)):
                    return "<0x1b>", 1
                base = chr(code)
                base = "<Space>" if base == " " else base
                return _modified(base, mods), i + 1
            if final == "~":
                key = parts[0] + "~"
            else:
                key = (parts[0] if parts[0] != "1" else "") + final
            name = _CSI_KEYS.get(key)
            if name is None:
                return "<0x1b>", 1
            return _modified(name, mods), i + 1
        if b1 == 0x4F:  # 'O'  SS3
            if len(buf) < 3:
                return None, 0
            name = _SS3_KEYS.get(chr(buf[2]))
            return (name, 3) if name else ("<0x1b>", 1)
        if 1 <= b1 <= 26:
            return "<Ctrl>-<Alt>-" + chr(96 + b1), 2
        n = _utf8_len(b1)
        if n == 0:
            return "<0x1b>", 1
        if len(buf) < 1 + n:
            return None, 0
        try:
            ch = buf[1:1 + n].decode("utf-8")
        except UnicodeDecodeError:
            return "<0x1b>", 1
        return "<Alt>-" + ch, 1 + n
    if b0 in _SINGLE:
        return _SINGLE[b0], 1
    if 1 <= b0 <= 26:
        return "<Ctrl>-" + chr(96 + b0), 1
    if b0 in _CTRL_PUNCT:
        return "<Ctrl>-" + _CTRL_PUNCT[b0], 1
    n = _utf8_len(b0)
    if n == 0:
        return "<0x%02x>" % b0, 1
    if len(buf) < n:
        return None, 0
    try:
        return buf[:n].decode("utf-8"), n
    except UnicodeDecodeError:
        return "<0x%02x>" % b0, 1


class KeyDecoder:
    def __init__(self) -> None:
        self._buf = b""
        self._t = 0.0

    def _drain(self, final: bool) -> list[tuple[float, str]]:
        out: list[tuple[float, str]] = []
        while self._buf:
            name, used = _parse_one(self._buf)
            if name is None:
                if not final:
                    break
                # Incomplete sequence at end: a lone escape is <Esc>, anything
                # else is shown byte by byte.
                if self._buf[0] == 0x1B:
                    out.append((self._t, "<Esc>"))
                else:
                    out.append((self._t, "<0x%02x>" % self._buf[0]))
                self._buf = self._buf[1:]
                continue
            out.append((self._t, name))
            self._buf = self._buf[used:]
        return out

    def feed(self, t: float, data: bytes) -> list[tuple[float, str]]:
        out: list[tuple[float, str]] = []
        if self._buf and t - self._t > ESC_TIMEOUT:
            out += self._drain(final=True)
        if not self._buf:
            self._t = t
        self._buf += data
        out += self._drain(final=False)
        return out

    def finish(self) -> list[tuple[float, str]]:
        return self._drain(final=True)
