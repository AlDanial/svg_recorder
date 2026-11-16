"""Mark the terminal's title bar while a recording is in progress.

The title is shown only on the user's live terminal; it never reaches the
recording.  Shells and full-screen programs routinely set the title themselves
(often on every prompt), so their title sequences are rewritten on the way to
the terminal to keep the marker in front of whatever they ask for.
"""

from __future__ import annotations

MARK = "🔴🔴🔴 RECORDING — svg_recorder 🔴🔴🔴"

_ESC = b"\x1b"
_OSC = b"\x1b]"
_BEL = b"\x07"
_ST = b"\x1b\\"
_MAX_PENDING = 4096  # an unterminated OSC longer than this is passed through as is


def _set_title(text: str) -> bytes:
    return _OSC + b"2;" + text.encode("utf-8") + _BEL


def begin() -> bytes:
    """Save the terminal's current title, then show the recording marker."""
    return b"\x1b[22;0t" + _set_title(MARK)


def end() -> bytes:
    """Clear the marker and restore the title saved by begin().

    Terminals without a title stack ignore the restore and are left with the
    empty title, which they show as their default.
    """
    return _set_title("") + b"\x1b[23;0t"


class TitleFilter:
    """Rewrite title-setting sequences (OSC 0 and OSC 2) to keep the marker.

    feed() takes program output in arbitrary chunks; a sequence split across
    chunks is held back until it is complete.
    """

    def __init__(self, mark: str = MARK):
        self._mark = mark.encode("utf-8")
        self._pending = b""

    def feed(self, data: bytes) -> bytes:
        data = self._pending + data
        self._pending = b""
        out = []
        pos = 0
        while True:
            start = data.find(_OSC, pos)
            if start < 0:
                break
            out.append(data[pos:start])
            bel = data.find(_BEL, start + 2)
            st = data.find(_ST, start + 2)
            ends = [(i, n) for i, n in ((bel, 1), (st, 2)) if i >= 0]
            if not ends:
                if len(data) - start > _MAX_PENDING:
                    out.append(data[start:])
                else:
                    self._pending = data[start:]
                return b"".join(out)
            stop, term_len = min(ends)
            out.append(self._rewrite(data[start + 2:stop], data[stop:stop + term_len]))
            pos = stop + term_len
        rest = data[pos:]
        if rest.endswith(_ESC):  # possibly the first half of an OSC introducer
            rest, self._pending = rest[:-1], _ESC
        out.append(rest)
        return b"".join(out)

    def flush(self) -> bytes:
        """Whatever is still held back, for when the output ends."""
        data, self._pending = self._pending, b""
        return data

    def _rewrite(self, body: bytes, terminator: bytes) -> bytes:
        kind, sep, text = body.partition(b";")
        if kind not in (b"0", b"2") or not sep:
            return _OSC + body + terminator
        marked = self._mark + (b" | " + text if text else b"")
        return _OSC + kind + b";" + marked + terminator
