# svg_recorder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `svg_recorder`, a CLI that records a terminal session to an asciicast file and renders it as a small animated SVG that emits only changed screen patches.

**Architecture:** Two stages joined by an asciicast v2 file. Recording spawns the user's shell in a pty and logs timestamped output and input bytes. Rendering replays the file through pyte, samples the screen at a fixed interval, diffs cells into rectangular patches, and writes each patch as one SVG group timed with CSS keyframes. A keystroke footer is rendered as extra virtual rows through the same diff path.

**Tech Stack:** Python 3.11+, pyte 0.8, wcwidth, setuptools, pytest, uv for environment management. No other runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-09-11-svg-recorder-design.md`

## Global Constraints

- Python `>=3.11`. Runtime dependencies are exactly `pyte` and `wcwidth`.
- Console script name is `svg_recorder`. Package import name is `svg_recorder`.
- Linux and macOS only in this plan. Recording lives behind the `Recorder` interface in `recorder.py`; only `recorder_posix.py` may import `pty`, `termios`, `tty`, `fcntl`, `select`.
- SVG output must contain no `<script>`, no `@import`, no `url(`, no `href` to anything except `#`-local ids, no `@font-face`. A test enforces this.
- SVG output has no indentation or newlines. Every numeric attribute is formatted with `fmt()` from `svgwriter.py` (no trailing zeros).
- Default time delta 0.05 s, default output `recording-YYYY-MM-DD-HH-MM-SS.svg`, default footer colors `#303030` background and `#f0f0f0` text, hold 2.0 s at end of loop, escape timeout 0.05 s, five keys in the footer, bold revert after 2.0 s.
- Cell geometry: width 8 px, height 17 px, font-size 14 px, baseline offset 13 px from the top of a row. Font stack `DejaVu Sans Mono,Menlo,Consolas,monospace`.
- All work happens in `/home/al/projects/svg_recorder/git`. Run tests with `uv run pytest -q`. Commit after every task with the attribution trailer given in the session reminder.
- The existing `tests/digits_of_pi.py`, `tests/server.py`, `tests/session.txt` are tdb fixtures for the benchmark. Do not move or edit them; `tests/session.txt` contains an absolute path to `digits_of_pi.py`.
- Scratch files go in `/tmp/claude-1000/-home-al-projects-svg-recorder/874eaf58-33bd-481c-96c7-dea57fd1ea1f/scratchpad`, referred to below as `$S`.

## File structure

```
git/
  pyproject.toml
  README.md
  .gitignore
  src/svg_recorder/
    __init__.py         __version__
    palette.py          Palette dataclass, KITTY_DEFAULT, OSC query bytes and reply parser, color resolution
    asciicast.py        Header, Event, Writer, read()
    keys.py             KeyDecoder: input bytes to key names with escape timeout
    annotations.py      Annotations, parse_annotations(), load_annotations(), AnnotationError
    patches.py          Cell, Patch, blank_frame(), row_runs(), diff_frames()
    screen.py           Footer, Sampler (pyte replay at fixed ticks, footer rows)
    svgwriter.py        fmt(), SvgWriter (style block, patch bodies, dedup, timing), check_self_contained()
    render.py           RenderOptions, render_events(), render_cast()
    recorder.py         Recorder protocol, RecordError, get_recorder()
    recorder_posix.py   PosixRecorder, build_script()
    cli.py              argument parsing and the two entry flows
  tools/
    sizes.py            size harness over render variants
    snapshot.sh         headless Chrome screenshot of an SVG at a playback time
  tests/
    test_package.py test_palette.py test_asciicast.py test_keys.py test_annotations.py
    test_patches.py test_screen.py test_svgwriter.py test_render.py
    test_recorder_posix.py test_cli.py
    (existing) digits_of_pi.py server.py session.txt
```

---

### Task 1: Project skeleton

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `README.md`, `src/svg_recorder/__init__.py`, `tests/test_package.py`

**Interfaces:**
- Produces: importable package `svg_recorder` with `__version__ = "0.1.0"`; `uv run pytest -q` works.

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "svg-recorder"
version = "0.1.0"
description = "Record a terminal session as a small animated SVG."
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [{name = "Al Danial", email = "al.danial@gmail.com"}]
keywords = ["svg", "recorder", "animation", "terminal"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX :: Linux",
    "Operating System :: MacOS",
    "Programming Language :: Python :: 3",
    "Topic :: Terminals",
]
dependencies = ["pyte>=0.8.0", "wcwidth>=0.2"]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov"]

[project.scripts]
svg_recorder = "svg_recorder.cli:main"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write .gitignore, README.md, package init**

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
build/
.pytest_cache/
.coverage
recording-*.svg
recording-*.cast
```

`README.md`:
```markdown
# svg_recorder

Record a terminal session as a small animated SVG.

    svg_recorder            # opens a shell; exit the shell to stop recording
    svg_recorder "cmd"      # records one command and stops when it exits
    svg_recorder render recording.cast -o out.svg

The SVG animates inside an `<img>` tag on GitHub and PyPI. On PyPI the README
must reference the absolute raw GitHub URL of the SVG, since PyPI cannot
resolve relative paths.
```

`src/svg_recorder/__init__.py`:
```python
"""Record a terminal session as a small animated SVG."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Write the smoke test**

`tests/test_package.py`:
```python
import svg_recorder


def test_version():
    assert svg_recorder.__version__ == "0.1.0"
```

- [ ] **Step 4: Sync the environment and run the test**

Run: `cd /home/al/projects/svg_recorder/git && uv sync --extra dev && uv run pytest -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore README.md src tests/test_package.py uv.lock
git commit -m "Project skeleton for svg_recorder"
```

---

### Task 2: Palette

**Files:**
- Create: `src/svg_recorder/palette.py`
- Test: `tests/test_palette.py`

**Interfaces:**
- Produces:
  - `Palette(fg: str, bg: str, colors: tuple[str, ...])` frozen dataclass; all values `#rrggbb` lowercase; `colors` has 16 entries.
  - `Palette.resolve(color: str, default: str) -> str` maps a pyte color value (`"default"`, a name like `"red"`, a hex string like `"ff8700"`, or `"#rrggbb"`) to `#rrggbb`.
  - `Palette.to_theme() -> dict` and `Palette.from_theme(d: dict) -> Palette` using asciinema's header shape `{"fg": "#..", "bg": "#..", "palette": "#..:#..:..."}`.
  - `KITTY_DEFAULT: Palette`.
  - `OSC_QUERY: bytes` to send to a terminal.
  - `apply_osc_replies(data: bytes, base: Palette) -> Palette`.
  - `ANSI_NAMES: list[str]` of the 16 names in index order.

- [ ] **Step 1: Write the failing tests**

`tests/test_palette.py`:
```python
from svg_recorder.palette import (
    KITTY_DEFAULT, OSC_QUERY, Palette, apply_osc_replies,
)


def test_kitty_default_shape():
    assert len(KITTY_DEFAULT.colors) == 16
    assert KITTY_DEFAULT.bg == "#000000"
    assert KITTY_DEFAULT.colors[1] == "#cc0403"


def test_resolve_named_hex_and_default():
    p = KITTY_DEFAULT
    assert p.resolve("default", "#123456") == "#123456"
    assert p.resolve("red", "#000000") == "#cc0403"
    assert p.resolve("brown", "#000000") == p.colors[3]
    assert p.resolve("brightred", "#000000") == "#f2201f"
    assert p.resolve("FF8700", "#000000") == "#ff8700"
    assert p.resolve("#abcdef", "#000000") == "#abcdef"
    assert p.resolve("nonsense", "#000000") == "#000000"


def test_theme_round_trip():
    d = KITTY_DEFAULT.to_theme()
    assert d["palette"].count(":") == 15
    assert Palette.from_theme(d) == KITTY_DEFAULT


def test_osc_query_contains_all_queries():
    assert b"\x1b]10;?\x1b\\" in OSC_QUERY
    assert b"\x1b]11;?\x1b\\" in OSC_QUERY
    for i in range(16):
        assert b"\x1b]4;%d;?\x1b\\" % i in OSC_QUERY


def test_apply_osc_replies_parses_16bit_and_8bit_and_bel():
    data = (b"\x1b]10;rgb:ffff/8080/0000\x1b\\"
            b"\x1b]11;rgb:10/20/30\x07"
            b"\x1b]4;3;rgb:abcd/ef01/2345\x1b\\"
            b"garbage")
    p = apply_osc_replies(data, KITTY_DEFAULT)
    assert p.fg == "#ff8000"
    assert p.bg == "#102030"
    assert p.colors[3] == "#abef23"
    assert p.colors[1] == KITTY_DEFAULT.colors[1]


def test_apply_osc_replies_ignores_out_of_range_index():
    p = apply_osc_replies(b"\x1b]4;99;rgb:ff/ff/ff\x1b\\", KITTY_DEFAULT)
    assert p == KITTY_DEFAULT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_palette.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'svg_recorder.palette'`

- [ ] **Step 3: Write the implementation**

`src/svg_recorder/palette.py`:
```python
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

_HEX6 = re.compile(r"[0-9a-fA-F]{6}")
_OSC_REPLY = re.compile(
    rb"\x1b\](10|11|4;(\d+));rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)(?:\x1b\\|\x07)"
)


@dataclass(frozen=True)
class Palette:
    fg: str
    bg: str
    colors: tuple[str, ...]

    def resolve(self, color: str, default: str) -> str:
        """Map a pyte color value to '#rrggbb'."""
        if color == "default":
            return default
        if color in _INDEX:
            return self.colors[_INDEX[color]]
        if color.startswith("#") and _HEX6.fullmatch(color[1:]):
            return color.lower()
        if _HEX6.fullmatch(color):
            return "#" + color.lower()
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_palette.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/svg_recorder/palette.py tests/test_palette.py
git commit -m "Add palette: defaults, OSC color queries, pyte color resolution"
```

---

### Task 3: Asciicast reader and writer

**Files:**
- Create: `src/svg_recorder/asciicast.py`
- Test: `tests/test_asciicast.py`

**Interfaces:**
- Consumes: `Palette`, `KITTY_DEFAULT` from Task 2.
- Produces:
  - `Header(width: int, height: int, timestamp: int, palette: Palette, cell: tuple[int, int] = (8, 17))` frozen dataclass with `to_json() -> str` and `Header.from_json(line: str) -> Header`.
  - `Event = tuple[float, str, bytes]` where the middle element is `"o"` or `"i"`.
  - `Writer(path, header)` context manager with `write(t: float, kind: str, data: bytes) -> None` and `close()`.
  - `read(path) -> tuple[Header, list[Event]]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_asciicast.py`:
```python
import json

from svg_recorder.asciicast import Header, Writer, read
from svg_recorder.palette import KITTY_DEFAULT


def test_header_json_round_trip():
    h = Header(80, 24, 1700000000, KITTY_DEFAULT, (8, 17))
    d = json.loads(h.to_json())
    assert d["version"] == 2 and d["width"] == 80 and d["height"] == 24
    assert d["theme"]["bg"] == "#000000"
    assert Header.from_json(h.to_json()) == h


def test_header_without_theme_uses_default():
    h = Header.from_json('{"version": 2, "width": 10, "height": 2, "timestamp": 5}')
    assert h.palette == KITTY_DEFAULT
    assert h.cell == (8, 17)


def test_write_and_read_events_preserve_split_utf8(tmp_path):
    path = tmp_path / "x.cast"
    h = Header(10, 2, 0, KITTY_DEFAULT)
    with Writer(path, h) as w:
        w.write(0.0, "o", b"ab\xe4\xbd")     # split multibyte char
        w.write(0.25, "o", b"\xa0c")
        w.write(0.5, "i", b"\x1b[A")
    header, events = read(path)
    assert header == h
    assert events == [(0.0, "o", b"ab\xe4\xbd"), (0.25, "o", b"\xa0c"), (0.5, "i", b"\x1b[A")]
    assert b"".join(d for _, k, d in events if k == "o").decode("utf-8") == "ab你c"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_asciicast.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/svg_recorder/asciicast.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_asciicast.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/svg_recorder/asciicast.py tests/test_asciicast.py
git commit -m "Add asciicast v2 reader and writer"
```

---

### Task 4: Key decoder

**Files:**
- Create: `src/svg_recorder/keys.py`
- Test: `tests/test_keys.py`

**Interfaces:**
- Produces:
  - `KeyDecoder()` with `feed(t: float, data: bytes) -> list[tuple[float, str]]` and `finish() -> list[tuple[float, str]]`.
  - `ESC_TIMEOUT = 0.05`.
  - Names exactly as in the spec: `<Ctrl>-x`, `<Alt>-x`, `<Ctrl>-<Alt>-x`, `<UpArrow>`, `<DownArrow>`, `<LeftArrow>`, `<RightArrow>`, `<PgUp>`, `<PgDn>`, `<Home>`, `<End>`, `<Insert>`, `<Delete>`, `<Tab>`, `<Esc>`, `<Enter>`, `<Space>`, `<Backspace>`, `<F1>`..`<F12>`; printable characters as themselves; unknown bytes as `<0x..>` per byte.

- [ ] **Step 1: Write the failing tests**

`tests/test_keys.py`:
```python
from svg_recorder.keys import KeyDecoder


def names(*chunks):
    d = KeyDecoder()
    out = []
    for t, data in chunks:
        out += d.feed(t, data)
    out += d.finish()
    return [n for _, n in out]


def test_printable_and_space():
    assert names((0, b"ab 1")) == ["a", "b", "<Space>", "1"]


def test_utf8_char_split_across_chunks():
    assert names((0, b"\xe4\xbd"), (0.01, b"\xa0")) == ["你"]


def test_control_letters_and_collisions():
    assert names((0, b"\x01\x18\x1a")) == ["<Ctrl>-a", "<Ctrl>-x", "<Ctrl>-z"]
    assert names((0, b"\x09\x0d\x0a\x7f\x08")) == [
        "<Tab>", "<Enter>", "<Enter>", "<Backspace>", "<Backspace>"]


def test_csi_and_ss3_keys():
    assert names((0, b"\x1b[A\x1b[B\x1b[C\x1b[D")) == [
        "<UpArrow>", "<DownArrow>", "<RightArrow>", "<LeftArrow>"]
    assert names((0, b"\x1b[5~\x1b[6~\x1b[H\x1b[F\x1b[2~\x1b[3~")) == [
        "<PgUp>", "<PgDn>", "<Home>", "<End>", "<Insert>", "<Delete>"]
    assert names((0, b"\x1bOP\x1b[15~\x1b[24~")) == ["<F1>", "<F5>", "<F12>"]


def test_csi_modifiers():
    assert names((0, b"\x1b[1;5A")) == ["<Ctrl>-<UpArrow>"]
    assert names((0, b"\x1b[3;3~")) == ["<Alt>-<Delete>"]


def test_alt_and_ctrl_alt():
    assert names((0, b"\x1bx")) == ["<Alt>-x"]
    assert names((0, b"\x1b\x02")) == ["<Ctrl>-<Alt>-b"]


def test_bare_escape_by_timeout_and_by_finish():
    assert names((0, b"\x1b"), (0.2, b"q")) == ["<Esc>", "q"]
    assert names((0, b"\x1b")) == ["<Esc>"]
    assert names((0, b"\x1b"), (0.01, b"[A")) == ["<UpArrow>"]


def test_timestamps_are_preserved():
    d = KeyDecoder()
    assert d.feed(1.5, b"a") == [(1.5, "a")]


def test_unknown_bytes_show_as_hex():
    assert names((0, b"\x1b[?99z")) == ["<0x1b>", "[", "?", "9", "9", "z"]
    assert names((0, b"\xff")) == ["<0xff>"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_keys.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/svg_recorder/keys.py`:
```python
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
                base = chr(int(parts[0]))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_keys.py -q`
Expected: `9 passed`. Note for `test_unknown_bytes_show_as_hex`: `0x3F` (`?`) is inside the CSI parameter byte range, so `\x1b[?99z` parses as a CSI sequence with an unknown key, yields `<0x1b>` for the escape, and the remaining bytes then parse one by one as printable characters. That is what the test expects.

- [ ] **Step 5: Commit**

```bash
git add src/svg_recorder/keys.py tests/test_keys.py
git commit -m "Add key decoder for footer keystroke names"
```

---

### Task 5: Annotation file parsing

**Files:**
- Create: `src/svg_recorder/annotations.py`
- Test: `tests/test_annotations.py`

**Interfaces:**
- Produces:
  - `AnnotationError(ValueError)` with attribute `line_no: int`; message formatted `"line N: <reason>"`.
  - `Annotations` with `modes: list[tuple[str, re.Pattern]]`, `entries: dict[tuple[str, str], str]`, `detect_mode(rows: Iterable[str]) -> str | None`, `describe(mode: str | None, key: str | None) -> str`.
  - `parse_annotations(text: str) -> Annotations`, `load_annotations(path) -> Annotations`.

- [ ] **Step 1: Write the failing tests**

`tests/test_annotations.py`:
```python
import pytest

from svg_recorder.annotations import AnnotationError, load_annotations, parse_annotations

SAMPLE = """
# comment
mode code-view-debug ^.*\\[DEBUG\\].*$
mode code-view-navigate \\[NAV\\]
code-view-debug <Ctrl>-b switch to breakpoint view
code-view-navigate / open search textbox
code-view-debug c continue execution
"""


def test_parse_modes_and_entries():
    a = parse_annotations(SAMPLE)
    assert [m for m, _ in a.modes] == ["code-view-debug", "code-view-navigate"]
    assert a.entries[("code-view-debug", "<Ctrl>-b")] == "switch to breakpoint view"
    assert a.entries[("code-view-navigate", "/")] == "open search textbox"


def test_detect_mode_first_match_wins_and_none():
    a = parse_annotations(SAMPLE)
    assert a.detect_mode(["hello", "status [NAV] x"]) == "code-view-navigate"
    assert a.detect_mode(["[DEBUG] [NAV]"]) == "code-view-debug"
    assert a.detect_mode(["nothing here"]) is None


def test_describe():
    a = parse_annotations(SAMPLE)
    assert a.describe("code-view-debug", "c") == "continue execution"
    assert a.describe("code-view-debug", "z") == ""
    assert a.describe(None, "c") == ""
    assert a.describe("code-view-debug", None) == ""


@pytest.mark.parametrize("text,line_no", [
    ("mode only-name\n", 1),
    ("mode bad-regex (\n", 1),
    ("\nsome-mode\n", 2),
    ("some-mode key\n", 1),
    ("undeclared-mode k description\n", 1),
])
def test_bad_lines_raise_with_line_number(text, line_no):
    with pytest.raises(AnnotationError) as info:
        parse_annotations(text)
    assert info.value.line_no == line_no
    assert str(info.value).startswith(f"line {line_no}:")


def test_load_annotations(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text(SAMPLE)
    assert load_annotations(p).describe("code-view-navigate", "/") == "open search textbox"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_annotations.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/svg_recorder/annotations.py`:
```python
"""Parse the --annotation file: mode regexes and per-mode keystroke descriptions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


class AnnotationError(ValueError):
    def __init__(self, line_no: int, reason: str):
        super().__init__(f"line {line_no}: {reason}")
        self.line_no = line_no


@dataclass
class Annotations:
    modes: list[tuple[str, re.Pattern]] = field(default_factory=list)
    entries: dict[tuple[str, str], str] = field(default_factory=dict)

    def detect_mode(self, rows: Iterable[str]) -> str | None:
        rows = list(rows)
        for name, pattern in self.modes:
            for row in rows:
                if pattern.search(row):
                    return name
        return None

    def describe(self, mode: str | None, key: str | None) -> str:
        if mode is None or key is None:
            return ""
        return self.entries.get((mode, key), "")


def parse_annotations(text: str) -> Annotations:
    result = Annotations()
    pending: list[tuple[int, str, str, str]] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=2)
        if parts[0] == "mode":
            if len(parts) < 3:
                raise AnnotationError(line_no, "mode line needs a name and a regex")
            try:
                pattern = re.compile(parts[2])
            except re.error as e:
                raise AnnotationError(line_no, f"bad regex: {e}") from None
            result.modes.append((parts[1], pattern))
            continue
        if len(parts) < 3:
            raise AnnotationError(line_no, "expected: <mode> <key> <description>")
        pending.append((line_no, parts[0], parts[1], parts[2]))
    declared = {name for name, _ in result.modes}
    for line_no, mode, key, desc in pending:
        if mode not in declared:
            raise AnnotationError(line_no, f"mode '{mode}' has no mode line")
        result.entries[(mode, key)] = desc
    return result


def load_annotations(path: str | Path) -> Annotations:
    return parse_annotations(Path(path).read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_annotations.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add src/svg_recorder/annotations.py tests/test_annotations.py
git commit -m "Add annotation file parsing and mode detection"
```

---

### Task 6: Patch detection

**Files:**
- Create: `src/svg_recorder/patches.py`
- Test: `tests/test_patches.py`

**Interfaces:**
- Produces:
  - `Cell(NamedTuple)`: `char: str, fg: str, bg: str, bold: bool, italic: bool, underline: bool, reverse: bool`. Colors are pyte values (`"default"`, name, hex) or `#rrggbb`.
  - `BLANK: Cell` = `Cell(" ", "default", "default", False, False, False, False)`.
  - `Frame = list[list[Cell]]`.
  - `blank_frame(cols: int, rows: int) -> Frame`.
  - `is_blank(cell: Cell) -> bool`: char is `" "` or `""`, bg default, not reverse.
  - `Patch` frozen dataclass: `col: int, row: int, width: int, rows: tuple[tuple[Cell, ...], ...], erase: bool`. `height` property = `len(rows)`.
  - `row_runs(old_row, new_row, gap: int) -> list[tuple[int, int]]` half-open column ranges.
  - `diff_frames(old: Frame, new: Frame, gap: int = 2, full_threshold: float = 0.5) -> list[Patch]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_patches.py`:
```python
from svg_recorder.patches import BLANK, blank_frame, diff_frames, is_blank, row_runs


def cell(ch, **kw):
    return BLANK._replace(char=ch, **kw)


def frame_from(lines, cols=None):
    cols = cols or max(len(l) for l in lines)
    return [[cell(ch) for ch in line.ljust(cols)] for line in lines]


def test_blank_frame_and_is_blank():
    f = blank_frame(3, 2)
    assert len(f) == 2 and len(f[0]) == 3 and f[1][2] == BLANK
    assert is_blank(BLANK) and is_blank(cell(""))
    assert not is_blank(cell("x"))
    assert not is_blank(cell(" ", bg="red"))
    assert not is_blank(cell(" ", reverse=True))


def test_row_runs_merges_small_gaps():
    old = frame_from(["abcdefghij"])[0]
    new = frame_from(["Xbcdefghij"])[0]
    assert row_runs(old, new, 2) == [(0, 1)]
    new = frame_from(["XbXdefXhiX"])[0]
    assert row_runs(old, new, 2) == [(0, 3), (6, 10)]
    assert row_runs(old, new, 0) == [(0, 1), (2, 3), (6, 7), (9, 10)]
    assert row_runs(old, old, 2) == []


def test_no_change_yields_nothing():
    f = frame_from(["hello", "world"])
    assert diff_frames(f, [list(r) for r in f]) == []


def test_single_character_patch():
    old = frame_from(["hello", "world"])
    new = frame_from(["hello", "wOrld"])
    [p] = diff_frames(old, new)
    assert (p.col, p.row, p.width, p.height) == (1, 1, 1, 1)
    assert p.rows == ((cell("O"),),)
    assert p.erase is True


def test_erase_false_when_old_region_blank():
    old = blank_frame(5, 2)
    new = frame_from(["     ", " ab  "])
    [p] = diff_frames(old, new)
    assert (p.col, p.row, p.width) == (1, 1, 2)
    assert p.erase is False


def test_stacked_runs_merge_into_rectangle():
    old = blank_frame(6, 4)
    new = frame_from(["      ", "  ab  ", "  cd  ", "      "])
    [p] = diff_frames(old, new)
    assert (p.col, p.row, p.width, p.height) == (2, 1, 2, 2)
    assert [c.char for c in p.rows[1]] == ["c", "d"]


def test_different_extents_stay_separate():
    old = blank_frame(6, 3)
    new = frame_from(["ab    ", "  cd  ", "  ef  "])
    ps = diff_frames(old, new)
    assert [(p.col, p.row, p.width, p.height) for p in ps] == [(0, 0, 2, 1), (2, 1, 2, 2)]


def test_whole_screen_when_over_threshold():
    old = frame_from(["aaaa", "aaaa"])
    new = frame_from(["bbbb", "bbba"])
    [p] = diff_frames(old, new, full_threshold=0.5)
    assert (p.col, p.row, p.width, p.height) == (0, 0, 4, 2)
    assert p.erase is True
    ps = diff_frames(old, new, full_threshold=1.0)
    assert [(p.col, p.row, p.width, p.height) for p in ps] == [(0, 0, 4, 1), (0, 1, 3, 1)]


def test_identical_row_objects_are_skipped():
    old = frame_from(["abc", "def"])
    new = [old[0], [cell("d"), cell("E"), cell("f")]]
    [p] = diff_frames(old, new)
    assert (p.col, p.row) == (1, 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_patches.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/svg_recorder/patches.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_patches.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add src/svg_recorder/patches.py tests/test_patches.py
git commit -m "Add cell diff and rectangular patch detection"
```

---

### Task 7: Screen sampler and footer

**Files:**
- Create: `src/svg_recorder/screen.py`
- Test: `tests/test_screen.py`

**Interfaces:**
- Consumes: `Header`, `Event` (Task 3); `KeyDecoder` (Task 4); `Annotations` (Task 5); `Cell`, `BLANK`, `Frame` (Task 6).
- Produces:
  - `FOOTER_KEYS = 5`, `BOLD_SECONDS = 2.0`.
  - `Footer(width: int, colors: tuple[str, str], annotations: Annotations | None = None)` with `push_key(t: float, name: str) -> None`, `height` property (1 or 2), `rows(t: float, screen_rows: list[str]) -> list[list[Cell]]`. `colors` is `(background, text)`.
  - `Sampler(header: Header, events: list[Event], time_delta: float = 0.05, footer: Footer | None = None, cursor: bool = False)` with `frames() -> Iterator[tuple[float, Frame]]` and `end_time` property (time of last event). Frames have `header.height + footer.height` rows. Unchanged rows keep their previous list object so `diff_frames` can skip them by identity.

- [ ] **Step 1: Write the failing tests**

`tests/test_screen.py`:
```python
from svg_recorder.annotations import parse_annotations
from svg_recorder.asciicast import Header
from svg_recorder.palette import KITTY_DEFAULT
from svg_recorder.patches import BLANK
from svg_recorder.screen import Footer, Sampler

COLORS = ("#303030", "#f0f0f0")


def text(row):
    return "".join(c.char for c in row)


def test_footer_shows_last_five_keys_newest_bold():
    f = Footer(30, COLORS)
    for i, k in enumerate("abcdefg"):
        f.push_key(i * 0.1, k)
    [row] = f.rows(0.7, [])
    assert text(row).rstrip() == "c d e f g"
    assert row[8].bold is True and row[8].char == "g"
    assert row[6].bold is False
    assert row[0].fg == "#f0f0f0" and row[0].bg == "#303030" and row[29].bg == "#303030"


def test_footer_bold_reverts_after_two_seconds():
    f = Footer(20, COLORS)
    f.push_key(1.0, "x")
    assert f.rows(2.9, [])[0][0].bold is True
    assert f.rows(3.05, [])[0][0].bold is False


def test_footer_truncates_to_width():
    f = Footer(4, COLORS)
    for k in ["<PgUp>", "<PgDn>"]:
        f.push_key(0, k)
    [row] = f.rows(0, [])
    assert len(row) == 4


def test_footer_annotation_row():
    a = parse_annotations("mode dbg \\[DEBUG\\]\ndbg c continue execution\n")
    f = Footer(30, COLORS, a)
    assert f.height == 2
    f.push_key(0, "c")
    rows = f.rows(0, ["x [DEBUG] y"])
    assert text(rows[1]).rstrip() == "continue execution"
    rows = f.rows(0, ["no mode here"])
    assert text(rows[1]).strip() == ""


def sampler(events, w=10, h=2, **kw):
    return Sampler(Header(w, h, 0, KITTY_DEFAULT), events, **kw)


def test_sampler_ticks_and_feeds_output():
    events = [(0.0, "o", b"ab"), (0.12, "o", b"\x1b[31mc")]
    frames = list(sampler(events, time_delta=0.05).frames())
    times = [t for t, _ in frames]
    assert times[:3] == [0.0, 0.05, 0.1]
    assert times[-1] >= 0.12
    assert text(frames[0][1][0]).rstrip() == "ab"
    last = frames[-1][1]
    assert text(last[0]).rstrip() == "abc" and last[0][2].fg == "red"
    assert last[1][0] == BLANK


def test_sampler_keeps_row_identity_when_unchanged():
    events = [(0.0, "o", b"ab"), (0.1, "o", b"\x1b[2;1Hzz")]
    frames = list(sampler(events).frames())
    assert frames[1][1][0] is frames[0][1][0]
    assert frames[-1][1][0] is frames[0][1][0]
    assert frames[-1][1][1] is not frames[0][1][1]


def test_sampler_cursor_marks_cell_reverse():
    events = [(0.0, "o", b"ab")]
    frames = list(sampler(events, cursor=True).frames())
    row = frames[-1][1][0]
    assert row[2].reverse is True and row[1].reverse is False
    frames = list(sampler([(0.0, "o", b"ab\x1b[?25l")], cursor=True).frames())
    assert frames[-1][1][0][2].reverse is False


def test_sampler_wide_char_continuation_cell_is_empty():
    frames = list(sampler([(0.0, "o", "你a".encode())]).frames())
    row = frames[-1][1][0]
    assert row[0].char == "你" and row[1].char == "" and row[2].char == "a"


def test_sampler_footer_rows_appended_and_keys_fed():
    f = Footer(10, COLORS)
    events = [(0.0, "o", b"x"), (0.02, "i", b"\x1b[A"), (0.3, "o", b"y")]
    frames = list(sampler(events, h=1, footer=f).frames())
    assert len(frames[0][1]) == 2
    assert text(frames[-1][1][1]).rstrip() == "<UpArrow>"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_screen.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/svg_recorder/screen.py`:
```python
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
            dirty = set(screen.dirty)
            screen.dirty.clear()
            if self.cursor:
                if prev_cursor_row is not None:
                    dirty.add(prev_cursor_row)
                if not screen.cursor.hidden:
                    dirty.add(screen.cursor.y)
            for r in dirty:
                if 0 <= r < h:
                    rows[r] = self._convert_row(screen, r)
            prev_cursor_row = None
            if self.cursor and not screen.cursor.hidden:
                cy, cx = screen.cursor.y, screen.cursor.x
                if cy < h and cx < w:
                    row = list(rows[cy])
                    row[cx] = row[cx]._replace(reverse=not row[cx].reverse)
                    rows[cy] = row
                    prev_cursor_row = cy
            if self.footer:
                texts = ["".join(c.char for c in rows[r]) for r in range(h)]
                for i, new_row in enumerate(self.footer.rows(t, texts)):
                    if new_row != rows[h + i]:
                        rows[h + i] = new_row
            yield t, list(rows)
            if t >= end:
                break
            tick_no += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_screen.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add src/svg_recorder/screen.py tests/test_screen.py
git commit -m "Add pyte sampler with fixed ticks, cursor, and footer rows"
```

---

### Task 8: SVG writer

**Files:**
- Create: `src/svg_recorder/svgwriter.py`
- Test: `tests/test_svgwriter.py`

**Interfaces:**
- Consumes: `Palette` (Task 2); `Cell`, `Patch` (Task 6).
- Produces:
  - `fmt(x: float) -> str` number formatting with no trailing zeros (`fmt(1.50) == "1.5"`, `fmt(3.0) == "3"`).
  - `FONT_FAMILY`, `FONT_SIZE = 14`, `BASELINE = 13`.
  - `SvgWriter(palette: Palette, cols: int, rows: int, cell: tuple[int, int] = (8, 17), loop: bool = True, hold: float = 2.0, dedup: bool = True)` with `add_frame(t: float, patches: list[Patch]) -> None` and `to_string(duration: float | None = None) -> str`. When `duration` is None it is the last frame time plus `hold`.
  - `check_self_contained(svg: str) -> list[str]` returns a list of violations (empty when the SVG has no external references or scripts).

- [ ] **Step 1: Write the failing tests**

`tests/test_svgwriter.py`:
```python
import re

from svg_recorder.palette import KITTY_DEFAULT
from svg_recorder.patches import BLANK, Patch
from svg_recorder.svgwriter import SvgWriter, check_self_contained, fmt


def cell(ch, **kw):
    return BLANK._replace(char=ch, **kw)


def patch(col, row, lines, erase=False, **kw):
    rows = tuple(tuple(cell(ch, **kw) for ch in line) for line in lines)
    return Patch(col, row, len(lines[0]), rows, erase)


def test_fmt():
    assert fmt(1.50) == "1.5" and fmt(3.0) == "3" and fmt(0.125) == "0.125" and fmt(12) == "12"


def test_document_shape_and_geometry():
    w = SvgWriter(KITTY_DEFAULT, 10, 2)
    w.add_frame(0.0, [patch(0, 0, ["hi"])])
    svg = w.to_string()
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert 'width="80" height="34"' in svg
    assert '<rect width="100%" height="100%" fill="#000000"/>' in svg
    assert "<text" in svg and ">hi</text>" in svg
    assert "\n" not in svg
    assert 'font-size:14px' in svg and 'DejaVu Sans Mono' in svg
    assert check_self_contained(svg) == []


def test_one_row_patch_positions_and_erase_rect():
    w = SvgWriter(KITTY_DEFAULT, 10, 3)
    w.add_frame(0.0, [patch(2, 1, ["ab"], erase=True)])
    svg = w.to_string()
    assert '<rect x="16" y="17" width="16" height="17" class="e"/>' in svg
    assert '<text x="16" y="30" textLength="16">ab</text>' in svg
    w = SvgWriter(KITTY_DEFAULT, 10, 3)
    w.add_frame(0.0, [patch(2, 1, ["ab"])])
    assert 'class="e"' not in w.to_string()


def test_multi_row_patch_uses_tspans():
    w = SvgWriter(KITTY_DEFAULT, 10, 3)
    w.add_frame(0.0, [patch(1, 0, ["ab", "cd"])])
    svg = w.to_string()
    assert ('<text x="8" y="13"><tspan textLength="16">ab</tspan>'
            '<tspan x="8" dy="17" textLength="16">cd</tspan></text>') in svg


def test_styles_become_classes_defined_once():
    w = SvgWriter(KITTY_DEFAULT, 10, 2)
    rows = ((cell("a", fg="red", bold=True), cell("b", fg="red", bold=True), cell("c", bg="ff8700")),)
    w.add_frame(0.0, [Patch(0, 0, 3, rows, False)])
    svg = w.to_string()
    assert svg.count("#f2201f") == 1            # bold red renders as bright red
    assert re.search(r'\.f\d+\{fill:#f2201f\}', svg)
    assert re.search(r'\.g\d+\{fill:#ff8700\}', svg)
    assert '.b{font-weight:bold}' in svg
    assert re.search(r'<rect x="16" y="0" width="8" height="17" class="g\d+"/>', svg)
    assert re.search(r'<tspan textLength="24" class="f\d+ b">ab</tspan>', svg) is None
    assert re.search(r'<tspan class="f\d+ b">ab</tspan><tspan>c</tspan>', svg)


def test_reverse_swaps_colors():
    w = SvgWriter(KITTY_DEFAULT, 10, 2)
    w.add_frame(0.0, [Patch(0, 0, 1, ((cell("r", reverse=True),),), False)])
    svg = w.to_string()
    assert re.search(r'\.g\d+\{fill:#dddddd\}', svg)   # bg takes default fg
    assert re.search(r'\.f\d+\{fill:#000000\}', svg)   # fg takes default bg


def test_text_is_escaped_and_wide_continuation_dropped():
    w = SvgWriter(KITTY_DEFAULT, 10, 2)
    w.add_frame(0.0, [Patch(0, 0, 4, ((cell("<"), cell("&"), cell("你"), cell("")),), False)])
    svg = w.to_string()
    assert '&lt;&amp;你</text>' in svg and 'textLength="32"' in svg


def test_loop_timing_classes_and_keyframes():
    w = SvgWriter(KITTY_DEFAULT, 10, 2, loop=True, hold=2.0)
    w.add_frame(0.0, [patch(0, 0, ["a"])])
    w.add_frame(1.0, [patch(0, 0, ["b"])])
    w.add_frame(3.0, [patch(0, 0, ["c"]), patch(0, 1, ["d"])])
    svg = w.to_string()
    # duration = 3 + 2 = 5 s; 1.0 s is 20%, 3.0 s is 60%
    assert '.t1{animation:a1 5s steps(1,end) infinite}' in svg
    assert '@keyframes a1{0%{visibility:hidden}20%{visibility:visible}}' in svg
    assert '@keyframes a2{0%{visibility:hidden}60%{visibility:visible}}' in svg
    assert svg.count('class="t2"') == 2
    assert '<g class="t1">' in svg
    assert 'class="t0"' not in svg          # frame at t=0 needs no class


def test_no_loop_uses_delays():
    w = SvgWriter(KITTY_DEFAULT, 10, 2, loop=False)
    w.add_frame(0.0, [patch(0, 0, ["a"])])
    w.add_frame(1.25, [patch(0, 0, ["b"])])
    svg = w.to_string()
    assert '[class^=t]{visibility:hidden;animation:s 1ms steps(1,end) forwards}' in svg
    assert '@keyframes s{to{visibility:visible}}' in svg
    assert '.t1{animation-delay:1.25s}' in svg
    assert 'infinite' not in svg


def test_dedup_moves_repeated_bodies_to_defs():
    w = SvgWriter(KITTY_DEFAULT, 10, 4)
    w.add_frame(0.0, [patch(0, 0, ["same"])])
    w.add_frame(1.0, [patch(2, 2, ["same"])])
    w.add_frame(2.0, [patch(0, 0, ["once"])])
    svg = w.to_string()
    assert '<defs><g id="p0">' in svg
    assert svg.count(">same<") == 1
    assert '<use href="#p0" x="0" y="0"/>' in svg
    assert '<use href="#p0" x="16" y="34" class="t1"/>' in svg
    assert ">once<" in svg
    assert check_self_contained(svg) == []
    w2 = SvgWriter(KITTY_DEFAULT, 10, 4, dedup=False)
    w2.add_frame(0.0, [patch(0, 0, ["same"])])
    w2.add_frame(1.0, [patch(2, 2, ["same"])])
    assert "<use" not in w2.to_string() and "<defs>" not in w2.to_string()


def test_check_self_contained_flags_violations():
    bad = '<svg><script>x</script><style>@import url(a.css)</style><a href="http://x"/></svg>'
    v = check_self_contained(bad)
    assert any("script" in x for x in v) and any("href" in x for x in v)
    assert any("url(" in x or "import" in x for x in v)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_svgwriter.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/svg_recorder/svgwriter.py`:
```python
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
        # text runs per row: list of (class, text)
        row_markup: list[list[tuple[str, str]]] = []
        for row in p.rows:
            runs: list[tuple[str, str]] = []
            for c in row:
                fg, _ = self._colors(c)
                cls = self._text_class(c, fg)
                if runs and runs[-1][0] == cls:
                    runs[-1] = (cls, runs[-1][1] + c.char)
                else:
                    runs.append((cls, c.char))
            row_markup.append(runs)
        if len(p.rows) == 1 and len(row_markup[0]) == 1:
            cls, text = row_markup[0][0]
            attr = f' class="{cls}"' if cls else ""
            out.append(f'<text x="{ox}" y="{oy + BASELINE}" textLength="{width_px}"{attr}>{_esc(text)}</text>')
            return "".join(out)
        parts = [f'<text x="{ox}" y="{oy + BASELINE}">']
        for ri, runs in enumerate(row_markup):
            for k, (cls, text) in enumerate(runs):
                attrs = ""
                if k == 0:
                    if ri > 0:
                        attrs += f' x="{ox}" dy="{ch}"'
                    if len(runs) == 1:
                        attrs += f' textLength="{width_px}"'
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_svgwriter.py -q`
Expected: `11 passed`. Note on `_colors`: pyte 0.8 names SGR 90..97 with the same names as 30..37, so bold plus a named dim color is mapped to the bright variant. That is the traditional terminal behavior and keeps output colorful. In `test_styles_become_classes_defined_once`, the row has two style runs so there is no single-run `textLength` on the tspans; the test asserts that.

- [ ] **Step 5: Commit**

```bash
git add src/svg_recorder/svgwriter.py tests/test_svgwriter.py
git commit -m "Add SVG writer with patch bodies, CSS timing, and dedup"
```

---

### Task 9: Render pipeline and snapshot tool

**Files:**
- Create: `src/svg_recorder/render.py`, `tools/snapshot.sh`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `read`, `Header`, `Event` (Task 3); `Annotations` (Task 5); `blank_frame`, `diff_frames` (Task 6); `Footer`, `Sampler` (Task 7); `SvgWriter`, `check_self_contained` (Task 8).
- Produces:
  - `RenderOptions` dataclass: `time_delta: float = 0.05, gap: int = 2, full_threshold: float = 0.5, dedup: bool = True, loop: bool = True, hold: float = 2.0, cursor: bool = False, footer: bool = False, footer_colors: tuple[str, str] = ("#303030", "#f0f0f0"), annotations: Annotations | None = None`.
  - `render_events(header: Header, events: list[Event], opts: RenderOptions) -> str`.
  - `render_cast(path, opts: RenderOptions) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_render.py`:
```python
from svg_recorder.annotations import parse_annotations
from svg_recorder.asciicast import Header, Writer
from svg_recorder.palette import KITTY_DEFAULT
from svg_recorder.render import RenderOptions, render_cast, render_events
from svg_recorder.svgwriter import check_self_contained

HEADER = Header(20, 3, 0, KITTY_DEFAULT)


def test_render_events_emits_only_changes():
    events = [(0.0, "o", b"hello"), (1.0, "o", b"\x1b[1;1HHello"), (2.0, "o", b"")]
    svg = render_events(HEADER, events, RenderOptions())
    assert svg.count("<text") == 2          # initial frame, then the one-cell patch
    assert ">H</text>" in svg
    assert check_self_contained(svg) == []


def test_render_footer_adds_rows_and_keys():
    events = [(0.0, "o", b"x"), (0.5, "i", b"q"), (1.0, "o", b"y")]
    svg = render_events(HEADER, events, RenderOptions(footer=True))
    assert 'height="68"' in svg               # 3 rows + 1 footer row, 17 px each
    assert ">q</text>" in svg or ">q</tspan>" in svg
    assert "#303030" in svg


def test_render_annotation_row():
    a = parse_annotations("mode m HELLO\nm q quit the program\n")
    events = [(0.0, "o", b"HELLO"), (0.5, "i", b"q")]
    svg = render_events(HEADER, events, RenderOptions(footer=True, annotations=a))
    assert 'height="85"' in svg
    assert "quit the program" in svg


def test_render_cast(tmp_path):
    p = tmp_path / "r.cast"
    with Writer(p, HEADER) as w:
        w.write(0.0, "o", b"abc")
    svg = render_cast(p, RenderOptions(loop=False))
    assert ">abc</text>" in svg and "infinite" not in svg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/svg_recorder/render.py`:
```python
"""Recording to SVG: sample, diff, write."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .annotations import Annotations
from .asciicast import Event, Header, read
from .patches import blank_frame, diff_frames
from .screen import Footer, Sampler
from .svgwriter import SvgWriter


@dataclass
class RenderOptions:
    time_delta: float = 0.05
    gap: int = 2
    full_threshold: float = 0.5
    dedup: bool = True
    loop: bool = True
    hold: float = 2.0
    cursor: bool = False
    footer: bool = False
    footer_colors: tuple[str, str] = ("#303030", "#f0f0f0")
    annotations: Annotations | None = None


def render_events(header: Header, events: list[Event], opts: RenderOptions) -> str:
    footer = Footer(header.width, opts.footer_colors, opts.annotations) if opts.footer else None
    sampler = Sampler(header, events, opts.time_delta, footer, opts.cursor)
    total_rows = header.height + (footer.height if footer else 0)
    writer = SvgWriter(header.palette, header.width, total_rows, header.cell,
                       loop=opts.loop, hold=opts.hold, dedup=opts.dedup)
    prev = blank_frame(header.width, total_rows)
    for t, frame in sampler.frames():
        patches = diff_frames(prev, frame, opts.gap, opts.full_threshold)
        if patches:
            writer.add_frame(t, patches)
        prev = frame
    return writer.to_string(sampler.end_time + opts.hold if opts.loop else None)


def render_cast(path: str | Path, opts: RenderOptions) -> str:
    header, events = read(path)
    return render_events(header, events, opts)
```

`tools/snapshot.sh` (make executable):
```bash
#!/bin/sh
# Screenshot an SVG as it looks N milliseconds into playback, using headless
# Chrome's virtual time so the CSS animation advances deterministically.
# Usage: tools/snapshot.sh file.svg milliseconds out.png
set -e
svg=$(realpath "$1"); ms=$2; out=$3
html=$(mktemp --suffix=.html)
printf '<html><body style="margin:0;background:#888"><img src="file://%s"></body></html>' "$svg" > "$html"
size=$(sed -n 's/.*width="\([0-9]*\)" height="\([0-9]*\)".*/\1,\2/p' "$svg" | head -1)
google-chrome --headless=new --disable-gpu --hide-scrollbars \
  --window-size="$size" --virtual-time-budget="$ms" \
  --screenshot="$out" "file://$html" 2>/dev/null
rm -f "$html"
echo "wrote $out"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `chmod +x tools/snapshot.sh && uv run pytest tests/test_render.py -q`
Expected: `4 passed`

- [ ] **Step 5: Visual check with a hand-written recording**

Write `$S/hand.cast` with exactly these five lines (the `` sequences are JSON escapes, typed literally):
```
{"version": 2, "width": 20, "height": 3, "timestamp": 0}
[0.0, "o", "[1;31mRed bold[0m plain"]
[1.0, "o", "[2;1H[44;97m blue bg [0m"]
[2.0, "o", "[1;5HXY"]
[3.0, "o", "[3;1H你好 wide"]
```
Then:
```bash
S=/tmp/claude-1000/-home-al-projects-svg-recorder/874eaf58-33bd-481c-96c7-dea57fd1ea1f/scratchpad
uv run svg_recorder render $S/hand.cast -o $S/hand.svg --cursor
tools/snapshot.sh $S/hand.svg 500 $S/t0.png
tools/snapshot.sh $S/hand.svg 2500 $S/t2.png
tools/snapshot.sh $S/hand.svg 3500 $S/t3.png
```
(If Task 11 is not done yet, use `uv run python -c "from svg_recorder.render import *; open('$S/hand.svg','w').write(render_cast('$S/hand.cast', RenderOptions(cursor=True)))"` instead of the CLI.)

Open the three PNGs with the Read tool. Expected: t0 shows only "Red bold plain" with the first two words in red bold; t2 additionally shows the blue background row and "XY" overwriting columns 5 and 6 of row 1; t3 shows the wide characters on row 3 with "wide" starting at column 5. Columns must line up between rows. If Chrome renders nothing, check `google-chrome --version` runs and that the HTML file path has no spaces.

- [ ] **Step 6: Commit**

```bash
git add src/svg_recorder/render.py tests/test_render.py tools/snapshot.sh
git commit -m "Add render pipeline and headless snapshot tool"
```

---

### Task 10: POSIX recorder

**Files:**
- Create: `src/svg_recorder/recorder.py`, `src/svg_recorder/recorder_posix.py`
- Test: `tests/test_recorder_posix.py`

**Interfaces:**
- Consumes: `Header`, `Writer` (Task 3); `KITTY_DEFAULT`, `OSC_QUERY`, `apply_osc_replies` (Task 2).
- Produces:
  - `RecordError(RuntimeError)`.
  - `Recorder` Protocol: `record(command: str | None, pre_commands: list[str], cast_path: Path) -> Header`.
  - `get_recorder() -> Recorder` raising `RecordError("recording is not supported on this platform")` on `win32`.
  - `PosixRecorder(term_in: int | None = None, term_out: int | None = None, shell: str | None = None, query_timeout: float = 0.2)`.
  - `build_script(pre_commands: list[str], command: str | None, shell: str, token: str) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_recorder_posix.py`:
```python
import fcntl
import os
import struct
import termios
import threading
import tty

import pytest

from svg_recorder.asciicast import read
from svg_recorder.recorder import RecordError, get_recorder
from svg_recorder.recorder_posix import PosixRecorder, build_script


class FakeTerminal:
    """A pty pair standing in for the user's real terminal."""

    def __init__(self, cols=40, lines=10):
        self.master, self.slave = os.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", lines, cols, 0, 0))
        tty.setraw(self.slave)
        self.seen = b""
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    def _drain(self):
        while True:
            try:
                data = os.read(self.master, 4096)
            except OSError:
                break
            if not data:
                break
            self.seen += data

    def type(self, data: bytes):
        os.write(self.master, data)

    def close(self):
        os.close(self.slave)
        os.close(self.master)


def record(term, command, pre=(), path=None):
    rec = PosixRecorder(term_in=term.slave, term_out=term.slave, shell="/bin/sh", query_timeout=0.05)
    return rec.record(command, list(pre), path)


def test_build_script_orders_pre_commands_clear_sentinel_command():
    s = build_script(["cd /tmp", "export A=1"], "echo hi", "/bin/sh", "TOK")
    assert s == "cd /tmp; export A=1; clear; printf '%s' TOK; echo hi"
    assert build_script([], None, "/bin/zsh", "TOK") == "clear; printf '%s' TOK; /bin/zsh"


def test_records_output_with_header_size_and_no_sentinel(tmp_path):
    term = FakeTerminal(cols=33, lines=7)
    path = tmp_path / "r.cast"
    header = record(term, "printf 'hello'; sleep 0.1; printf '\\033[31mworld'", path=path)
    term.close()
    assert (header.width, header.height) == (33, 7)
    h2, events = read(path)
    assert h2 == header
    out = b"".join(d for _, k, d in events if k == "o")
    assert b"hello" in out and b"\x1b[31mworld" in out
    assert b"printf" not in out and b"SVGREC" not in out
    times = [t for t, _, _ in events]
    assert times == sorted(times) and times[0] >= 0
    assert b"hello" in term.seen and b"world" in term.seen


def test_pre_commands_affect_environment_and_are_not_recorded(tmp_path):
    term = FakeTerminal()
    path = tmp_path / "r.cast"
    record(term, 'printf "%s" "$FOO-$PWD"', pre=["export FOO=bar", "cd /tmp"], path=path)
    term.close()
    _, events = read(path)
    out = b"".join(d for _, k, d in events if k == "o")
    assert out.strip() == b"bar-/tmp"


def test_input_is_forwarded_and_recorded(tmp_path):
    term = FakeTerminal()
    path = tmp_path / "r.cast"
    threading.Timer(0.3, term.type, args=(b"q\n",)).start()
    record(term, "read x; printf 'got:%s' \"$x\"", path=path)
    term.close()
    _, events = read(path)
    assert any(k == "i" and d == b"q\n" for _, k, d in events)
    out = b"".join(d for _, k, d in events if k == "o")
    assert b"got:q" in out


def test_palette_reply_is_captured(tmp_path):
    term = FakeTerminal()
    term.type(b"\x1b]11;rgb:1111/2222/3333\x1b\\")
    header = record(term, "true", path=tmp_path / "r.cast")
    term.close()
    assert header.palette.bg == "#112233"


def test_failed_pre_command_raises(tmp_path):
    term = FakeTerminal()
    with pytest.raises(RecordError):
        record(term, "true", pre=["exit 3"], path=tmp_path / "r.cast")
    term.close()


def test_get_recorder_returns_posix_here():
    assert isinstance(get_recorder(), PosixRecorder)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_recorder_posix.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the interface module**

`src/svg_recorder/recorder.py`:
```python
"""Recorder interface and platform selection."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol

from .asciicast import Header


class RecordError(RuntimeError):
    pass


class Recorder(Protocol):
    def record(self, command: str | None, pre_commands: list[str], cast_path: Path) -> Header:
        """Record a session to cast_path and return its header."""


def get_recorder() -> Recorder:
    if sys.platform == "win32":
        raise RecordError("recording is not supported on this platform")
    from .recorder_posix import PosixRecorder
    return PosixRecorder()
```

- [ ] **Step 4: Write the POSIX recorder**

`src/svg_recorder/recorder_posix.py`:
```python
"""Record a shell session through a pty on Linux and macOS."""

from __future__ import annotations

import fcntl
import os
import pty
import secrets
import select
import struct
import sys
import termios
import time
import tty
from pathlib import Path

from .asciicast import Header, Writer
from .palette import KITTY_DEFAULT, OSC_QUERY, Palette, apply_osc_replies
from .recorder import RecordError


def build_script(pre_commands: list[str], command: str | None, shell: str, token: str) -> str:
    """The -c script: pre-commands, clear, sentinel, then the command or a shell."""
    parts = list(pre_commands) + ["clear", f"printf '%s' {token}", command or shell]
    return "; ".join(parts)


class PosixRecorder:
    def __init__(self, term_in: int | None = None, term_out: int | None = None,
                 shell: str | None = None, query_timeout: float = 0.2):
        self.term_in = sys.stdin.fileno() if term_in is None else term_in
        self.term_out = sys.stdout.fileno() if term_out is None else term_out
        self.shell = shell or os.environ.get("SHELL") or "/bin/sh"
        self.query_timeout = query_timeout

    # ----- helpers --------------------------------------------------------

    def _size(self) -> tuple[int, int]:
        try:
            cols, lines = os.get_terminal_size(self.term_out)
            return cols, lines
        except OSError:
            return 80, 24

    def _query_palette(self) -> Palette:
        try:
            os.write(self.term_out, OSC_QUERY)
        except OSError:
            return KITTY_DEFAULT
        buf = b""
        deadline = time.monotonic() + self.query_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = select.select([self.term_in], [], [], remaining)
            if not ready:
                break
            try:
                data = os.read(self.term_in, 4096)
            except OSError:
                break
            if not data:
                break
            buf += data
        return apply_osc_replies(buf, KITTY_DEFAULT)

    @staticmethod
    def _write_all(fd: int, data: bytes) -> None:
        while data:
            n = os.write(fd, data)
            data = data[n:]

    # ----- main -----------------------------------------------------------

    def record(self, command: str | None, pre_commands: list[str], cast_path: Path) -> Header:
        cols, lines = self._size()
        saved = None
        if os.isatty(self.term_in):
            saved = termios.tcgetattr(self.term_in)
            tty.setraw(self.term_in, termios.TCSANOW)  # TCSANOW: do not flush pending input
        try:
            palette = self._query_palette()
            token = "SVGREC" + secrets.token_hex(8)
            script = build_script(pre_commands, command, self.shell, token)
            pid, master = pty.fork()
            if pid == 0:  # child
                try:
                    os.execvp(self.shell, [self.shell, "-c", script])
                finally:
                    os._exit(127)
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", lines, cols, 0, 0))
            try:
                rest = self._wait_for_sentinel(master, token.encode())
                header = Header(cols, lines, int(time.time()), palette)
                with Writer(cast_path, header) as writer:
                    self._shuttle(master, writer, rest)
            finally:
                os.close(master)
                os.waitpid(pid, 0)
            return header
        finally:
            if saved is not None:
                termios.tcsetattr(self.term_in, termios.TCSADRAIN, saved)

    def _read_master(self, master: int) -> bytes:
        try:
            return os.read(master, 65536)
        except OSError:  # EIO when the child closes the slave
            return b""

    def _read_term(self) -> bytes:
        try:
            return os.read(self.term_in, 4096)
        except OSError:
            return b""

    def _wait_for_sentinel(self, master: int, token: bytes) -> bytes:
        buf = b""
        watch_in = True
        while True:
            fds = [master] + ([self.term_in] if watch_in else [])
            ready, _, _ = select.select(fds, [], [])
            if master in ready:
                data = self._read_master(master)
                if not data:
                    raise RecordError("shell exited before recording started (pre-commands failed?)")
                buf += data
                i = buf.find(token)
                if i >= 0:
                    return buf[i + len(token):]
                buf = buf[-len(token):]  # keep a tail in case the token straddles reads
            if self.term_in in ready:
                data = self._read_term()
                if not data:
                    watch_in = False
                else:
                    self._write_all(master, data)

    def _shuttle(self, master: int, writer: Writer, first: bytes) -> None:
        t0 = time.monotonic()
        if first:
            self._write_all(self.term_out, first)
            writer.write(0.0, "o", first)
        watch_in = True
        while True:
            fds = [master] + ([self.term_in] if watch_in else [])
            ready, _, _ = select.select(fds, [], [])
            if master in ready:
                data = self._read_master(master)
                if not data:
                    return
                self._write_all(self.term_out, data)
                writer.write(time.monotonic() - t0, "o", data)
            if self.term_in in ready:
                data = self._read_term()
                if not data:
                    watch_in = False
                    continue
                self._write_all(master, data)
                writer.write(time.monotonic() - t0, "i", data)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_recorder_posix.py -q`
Expected: `7 passed`. Notes: `_query_palette` runs before the fork, so the palette test types its reply before calling `record`. On Linux, reading the master after the child exits raises `EIO`, which `_read_master` turns into end of stream. If `test_failed_pre_command_raises` hangs, check that `/bin/sh -c "exit 3; clear; ..."` really exits; dash and bash both do.

- [ ] **Step 6: Commit**

```bash
git add src/svg_recorder/recorder.py src/svg_recorder/recorder_posix.py tests/test_recorder_posix.py
git commit -m "Add POSIX pty recorder behind the Recorder interface"
```

---

### Task 11: Command line interface

**Files:**
- Create: `src/svg_recorder/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_annotations`, `AnnotationError` (Task 5); `RenderOptions`, `render_cast` (Task 9); `get_recorder`, `RecordError` (Task 10).
- Produces: `main(argv: list[str] | None = None) -> int`; `build_parsers() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]` (record parser, render parser); `options_from_args(args) -> RenderOptions`; `default_output_name(now: datetime | None = None) -> str`; `read_pre_commands(args) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
import gzip
from datetime import datetime

from svg_recorder import cli
from svg_recorder.asciicast import Header, Writer
from svg_recorder.palette import KITTY_DEFAULT


def make_cast(path):
    with Writer(path, Header(10, 2, 0, KITTY_DEFAULT)) as w:
        w.write(0.0, "o", b"hi")
        w.write(0.3, "i", b"k")
    return path


def test_default_output_name():
    assert cli.default_output_name(datetime(2026, 9, 11, 8, 5, 9)) == "recording-2026-09-11-08-05-09.svg"


def test_render_subcommand_writes_svg(tmp_path):
    cast = make_cast(tmp_path / "a.cast")
    out = tmp_path / "a.svg"
    assert cli.main(["render", str(cast), "-o", str(out), "--no-loop", "-t", "0.1"]) == 0
    svg = out.read_text()
    assert ">hi</text>" in svg and "infinite" not in svg


def test_render_footer_and_annotation_options(tmp_path):
    cast = make_cast(tmp_path / "a.cast")
    ann = tmp_path / "ann.txt"
    ann.write_text("mode m hi\nm k key k does things\n")
    out = tmp_path / "a.svg"
    rc = cli.main(["render", str(cast), "-o", str(out), "-f", "-a", str(ann),
                   "--footer-colors", "#111111", "#eeeeee"])
    assert rc == 0
    svg = out.read_text()
    assert "key k does things" in svg and "#111111" in svg


def test_gzip_output(tmp_path):
    cast = make_cast(tmp_path / "a.cast")
    out = tmp_path / "a.svgz"
    assert cli.main(["render", str(cast), "-o", str(out), "--gzip"]) == 0
    assert b"<svg" in gzip.decompress(out.read_bytes())


def test_bad_annotation_file_fails_before_recording(tmp_path, capsys):
    ann = tmp_path / "ann.txt"
    ann.write_text("mode\n")
    rc = cli.main(["-f", "-a", str(ann), "true"])
    assert rc == 2
    assert "line 1" in capsys.readouterr().err


def test_missing_pre_commands_file_fails(tmp_path, capsys):
    rc = cli.main(["-F", str(tmp_path / "nope.txt"), "true"])
    assert rc == 2
    assert "nope.txt" in capsys.readouterr().err


def test_read_pre_commands_merges_file_then_string(tmp_path):
    f = tmp_path / "pre.txt"
    f.write_text("# c\ncd /tmp\n\nexport A=1\n")
    rec_parser, _ = cli.build_parsers()
    args = rec_parser.parse_args(["-F", str(f), "-c", "export B=2; export C=3"])
    assert cli.read_pre_commands(args) == ["cd /tmp", "export A=1", "export B=2", "export C=3"]


def test_record_flow_uses_recorder_and_keeps_cast(tmp_path, monkeypatch):
    calls = {}

    class FakeRecorder:
        def record(self, command, pre_commands, cast_path):
            calls["command"] = command
            calls["pre"] = pre_commands
            make_cast(cast_path)
            return Header(10, 2, 0, KITTY_DEFAULT)

    monkeypatch.setattr(cli, "get_recorder", lambda: FakeRecorder())
    out = tmp_path / "s.svg"
    rc = cli.main(["-o", str(out), "--keep-recording", "-c", "export X=1", "some command"])
    assert rc == 0
    assert calls == {"command": "some command", "pre": ["export X=1"]}
    assert out.exists() and (tmp_path / "s.cast").exists()


def test_record_flow_discards_cast_by_default(tmp_path, monkeypatch):
    class FakeRecorder:
        def record(self, command, pre_commands, cast_path):
            make_cast(cast_path)
            return Header(10, 2, 0, KITTY_DEFAULT)

    monkeypatch.setattr(cli, "get_recorder", lambda: FakeRecorder())
    out = tmp_path / "s.svg"
    assert cli.main(["-o", str(out)]) == 0
    assert out.exists() and not (tmp_path / "s.cast").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`src/svg_recorder/cli.py`:
```python
"""Command line entry point."""

from __future__ import annotations

import argparse
import gzip
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import __version__
from .annotations import AnnotationError, load_annotations
from .recorder import RecordError, get_recorder
from .render import RenderOptions, render_cast


def default_output_name(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return now.strftime("recording-%Y-%m-%d-%H-%M-%S.svg")


def _add_render_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-t", "--time-delta", type=float, default=0.05, metavar="SECONDS",
                   help="seconds between frame captures (default 0.05)")
    p.add_argument("-f", "--footer", action="store_true", help="show the last keystrokes in a footer row")
    p.add_argument("-a", "--annotation", metavar="FILE",
                   help="with --footer, add a row describing the current keystroke")
    p.add_argument("--footer-colors", nargs=2, metavar=("BG", "FG"), default=["#303030", "#f0f0f0"],
                   help="footer background and text colors")
    p.add_argument("-o", "--output", metavar="FILE", help="SVG output file")
    p.add_argument("--cursor", action="store_true", help="render the cursor")
    p.add_argument("--no-loop", action="store_true", help="play once instead of looping")
    p.add_argument("--gzip", action="store_true", help="write gzip compressed output")
    p.add_argument("--gap", type=int, default=2, help=argparse.SUPPRESS)
    p.add_argument("--full-threshold", type=float, default=0.5, help=argparse.SUPPRESS)
    p.add_argument("--no-dedup", action="store_true", help=argparse.SUPPRESS)


def build_parsers() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    rec = argparse.ArgumentParser(prog="svg_recorder",
                                  description="Record a terminal session as a small animated SVG.",
                                  epilog="Use 'svg_recorder render FILE.cast' to render a saved recording.")
    rec.add_argument("-v", "--version", action="version", version=f"svg_recorder {__version__}")
    rec.add_argument("-c", "--pre-commands", metavar="COMMANDS",
                     help="semicolon delimited shell commands to run before recording starts")
    rec.add_argument("-F", "--pre-commands-file", metavar="FILE",
                     help="file of shell commands to run before recording starts")
    rec.add_argument("--keep-recording", action="store_true",
                     help="keep the intermediate .cast file next to the SVG")
    _add_render_options(rec)
    rec.add_argument("command", nargs="?", help="command to record; omit for an interactive shell")

    ren = argparse.ArgumentParser(prog="svg_recorder render",
                                  description="Render a saved recording to SVG.")
    ren.add_argument("cast", help="asciicast v2 file")
    _add_render_options(ren)
    return rec, ren


def read_pre_commands(args: argparse.Namespace) -> list[str]:
    commands: list[str] = []
    if args.pre_commands_file:
        text = Path(args.pre_commands_file).read_text(encoding="utf-8")
        commands += [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    if args.pre_commands:
        commands += [c.strip() for c in args.pre_commands.split(";") if c.strip()]
    return commands


def options_from_args(args: argparse.Namespace) -> RenderOptions:
    annotations = load_annotations(args.annotation) if args.annotation else None
    return RenderOptions(
        time_delta=args.time_delta,
        gap=args.gap,
        full_threshold=args.full_threshold,
        dedup=not args.no_dedup,
        loop=not args.no_loop,
        cursor=args.cursor,
        footer=args.footer or bool(args.annotation),
        footer_colors=(args.footer_colors[0], args.footer_colors[1]),
        annotations=annotations,
    )


def _write_output(svg: str, path: Path, compress: bool) -> None:
    if compress:
        path.write_bytes(gzip.compress(svg.encode("utf-8")))
    else:
        path.write_text(svg, encoding="utf-8")


def _fail(msg: str) -> int:
    print(f"svg_recorder: {msg}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    rec_parser, ren_parser = build_parsers()

    if argv and argv[0] == "render":
        args = ren_parser.parse_args(argv[1:])
        try:
            opts = options_from_args(args)
        except (AnnotationError, OSError) as e:
            return _fail(f"annotation file: {e}")
        output = Path(args.output or Path(args.cast).with_suffix(".svg").name)
        try:
            svg = render_cast(args.cast, opts)
        except OSError as e:
            return _fail(str(e))
        _write_output(svg, output, args.gzip)
        print(f"wrote {output}", file=sys.stderr)
        return 0

    args = rec_parser.parse_args(argv)
    try:
        opts = options_from_args(args)
    except AnnotationError as e:
        return _fail(f"annotation file {args.annotation}: {e}")
    except OSError as e:
        return _fail(f"annotation file: {e}")
    try:
        pre_commands = read_pre_commands(args)
    except OSError as e:
        return _fail(f"pre-commands file: {e}")

    output = Path(args.output or default_output_name())
    if args.keep_recording:
        cast_path = output.with_suffix(".cast")
        tmp = None
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".cast", delete=False)
        tmp.close()
        cast_path = Path(tmp.name)
    try:
        try:
            get_recorder().record(args.command, pre_commands, cast_path)
        except RecordError as e:
            return _fail(str(e))
        svg = render_cast(cast_path, opts)
        _write_output(svg, output, args.gzip)
    finally:
        if tmp is not None:
            cast_path.unlink(missing_ok=True)
    print(f"wrote {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -q && uv run pytest -q`
Expected: `9 passed` for the CLI file and the whole suite green.

- [ ] **Step 5: Smoke test the installed script end to end**

This needs a tty on stdin. If the harness has none (check with `[ -t 0 ] && echo tty || echo no-tty`), skip to Step 6 and say so in the task report.
```bash
cd /home/al/projects/svg_recorder/git
S=/tmp/claude-1000/-home-al-projects-svg-recorder/874eaf58-33bd-481c-96c7-dea57fd1ea1f/scratchpad
uv run svg_recorder -o $S/smoke.svg --keep-recording -c "export GREETING=hi" 'printf "$GREETING\n"; sleep 0.3; printf "\033[32mdone\033[0m\n"'
ls -la $S/smoke.*
grep -c "done" $S/smoke.svg
```
Expected: both files exist, the terminal is back in normal mode (typing echoes), and the SVG contains `hi` and `done`.

- [ ] **Step 6: Commit**

```bash
git add src/svg_recorder/cli.py tests/test_cli.py
git commit -m "Add svg_recorder command line interface"
```

---

### Task 12: Size harness, benchmark recording, and baseline

**Files:**
- Create: `tools/sizes.py`, `tests/benchmark.cast` (recorded by the user), `docs/benchmarks.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `read` (Task 3); `RenderOptions`, `render_events` (Task 9).
- Produces: `tools/sizes.py CAST...` printing a table of bytes per variant per recording, plus gzip size for the default variant.

- [ ] **Step 1: Write the harness**

`tools/sizes.py`:
```python
#!/usr/bin/env python3
"""Render recordings under several strategy variants and print output sizes.

Usage: uv run python tools/sizes.py tests/benchmark.cast [more.cast ...]
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from svg_recorder.asciicast import read  # noqa: E402
from svg_recorder.render import RenderOptions, render_events  # noqa: E402

VARIANTS = {
    "default": RenderOptions(),
    "gap0": RenderOptions(gap=0),
    "gap4": RenderOptions(gap=4),
    "full-never": RenderOptions(full_threshold=1.01),
    "full-0.25": RenderOptions(full_threshold=0.25),
    "no-dedup": RenderOptions(dedup=False),
    "no-loop": RenderOptions(loop=False),
    "delta-0.1": RenderOptions(time_delta=0.1),
    "footer": RenderOptions(footer=True),
}


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        return 2
    casts = [(Path(p).name, *read(p)) for p in paths]
    width = max(len(n) for n in VARIANTS) + 4
    print("variant".ljust(width) + "".join(name.rjust(18) for name, _, _ in casts))
    for name, opts in VARIANTS.items():
        row = name.ljust(width)
        for _, header, events in casts:
            row += f"{len(render_events(header, events, opts).encode()):>18,}"
        print(row)
    row = "default+gzip".ljust(width)
    for _, header, events in casts:
        row += f"{len(gzip.compress(render_events(header, events, RenderOptions()).encode())):>18,}"
    print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 2: Run the harness on a synthetic recording to prove it works**

Write `$S/make_synth.py`:
```python
import sys
from svg_recorder.asciicast import Header, Writer
from svg_recorder.palette import KITTY_DEFAULT

path = sys.argv[1]
with Writer(path, Header(80, 24, 0, KITTY_DEFAULT)) as w:
    for i in range(200):
        w.write(i * 0.1, "o", b"\x1b[%d;1H\x1b[3%dmtick %d\x1b[0m" % (1 + i % 24, i % 7 + 1, i))
        if i % 10 == 0:
            w.write(i * 0.1 + 0.01, "i", b"j")
```
Run:
```bash
S=/tmp/claude-1000/-home-al-projects-svg-recorder/874eaf58-33bd-481c-96c7-dea57fd1ea1f/scratchpad
uv run python $S/make_synth.py $S/synth.cast
uv run python tools/sizes.py $S/synth.cast
```
Expected: a table with nine variant rows plus the gzip row, every value a positive byte count, `no-dedup` at least as large as `default`, and `delta-0.1` no larger than `default`.

- [ ] **Step 3: Record the benchmark (user action)**

This step must be done by the user in a kitty window; an agent cannot drive a GUI terminal. Ask the user to run:

```bash
cd /home/al/projects/svg_recorder/git
uv run svg_recorder --keep-recording -o tests/benchmark.svg
```
then in the new shell:
```bash
cd tests
tdb --replay-quiet --replay-interval 0.5 --replay-tui session.txt
exit
```
This leaves `tests/benchmark.cast` and `tests/benchmark.svg`. Only the cast is committed; delete `tests/benchmark.svg` after looking at it in a browser.

- [ ] **Step 4: Produce the termtosvg baseline**

```bash
S=/tmp/claude-1000/-home-al-projects-svg-recorder/874eaf58-33bd-481c-96c7-dea57fd1ea1f/scratchpad
uv tool install termtosvg 2>&1 | tail -2
termtosvg render tests/benchmark.cast $S/baseline.svg
ls -l $S/baseline.svg
uv run python tools/sizes.py tests/benchmark.cast
```
If termtosvg fails to install on Python 3.14, retry with `uv tool install --python 3.11 termtosvg`. If it still fails, record that in `docs/benchmarks.md` and use the theoretical estimate from the spec instead. termtosvg reads asciicast v2 and ignores the extra header keys.

- [ ] **Step 5: Write docs/benchmarks.md and update README**

`docs/benchmarks.md` records: the date, the commit, the termtosvg version and baseline size, the full harness table for `tests/benchmark.cast`, and the ratio of `default` to the baseline. Add to `README.md` a "Benchmarks" section with two lines: the default size versus termtosvg for the tdb session, and the command to reproduce (`uv run python tools/sizes.py tests/benchmark.cast`). Also add one line under usage: pre-commands run in a non-interactive shell, so put aliases in your shell rc file rather than in pre-commands.

- [ ] **Step 6: Visual check of the benchmark**

```bash
S=/tmp/claude-1000/-home-al-projects-svg-recorder/874eaf58-33bd-481c-96c7-dea57fd1ea1f/scratchpad
uv run svg_recorder render tests/benchmark.cast -o $S/bench.svg -f
tools/snapshot.sh $S/bench.svg 3000 $S/bench3.png
tools/snapshot.sh $S/bench.svg 15000 $S/bench15.png
```
Open both PNGs with the Read tool. Expected: a recognizable tdb TUI with aligned columns and a footer row at the bottom; the two snapshots differ where the replay advanced.

- [ ] **Step 7: Run the full suite and commit**

```bash
uv run pytest -q
git add tools/sizes.py tests/benchmark.cast docs/benchmarks.md README.md
git commit -m "Add size harness, benchmark recording, and termtosvg baseline"
```

---

## Self-review

**Spec coverage.** Section 2 options: all in Task 11 (`-t`, `-c`, `-F`, `-f`, `-a`, `--footer-colors`, `-o`, `--cursor`, `--no-loop`, `--keep-recording`, `--gzip`, positional command, `render` subcommand). Section 3 recording: Task 10, including sentinel, palette query, size, raw mode and restore, and child death (the writer is closed by its context manager, so the CLI renders whatever was captured). Section 3 intermediate format: Task 3, using asciinema's `theme` key for the palette. Section 4.1 sampling: Task 7. Section 4.2 patches, gap, threshold, cursor: Tasks 6 and 7. Section 4.3 structure, `textLength`, classes, font, wide chars: Task 8. Section 4.4 timing in both modes and the hold: Task 8. Section 4.5 dedup and byte discipline: Task 8. Section 5 footer, key names, bold revert, annotation grammar and errors: Tasks 4, 5, 7. Section 6 tests, harness, snapshot, baseline: Tasks 9 and 12. Section 7 layout and packaging: Task 1.

**Deviations from the spec, each deliberate:**
1. The erase rect is dropped whenever the old region was blank, not only for one-row patches with default background, because a one-row patch drawn over old glyphs must still erase them. This is strictly smaller and always correct.
2. Bold revert in the footer is computed at each tick from the last key time instead of by scheduling a change; the visible result is identical at tick resolution.
3. Pre-commands run inside `$SHELL -c`, so exported variables and `cd` carry into the recorded command but shell aliases and functions do not, because the interactive shell is a child process. The README says to put aliases in the shell rc file.
4. `textLength` is set on each row tspan rather than once on the text element, because per-chunk lengths are the form browsers handle consistently.

**Placeholder scan.** No TBD or TODO. Every code step has full code. Task 12 Step 3 is a genuine user action and is labeled as such.

**Type consistency.** `Header(width, height, timestamp, palette, cell)` is used identically in Tasks 3, 7, 9, 10, 11, 12. `Event = (float, str, bytes)` throughout. `Patch(col, row, width, rows, erase)` in Tasks 6, 8, 9. `Footer(width, colors, annotations)` and `Footer.rows(t, screen_rows)` in Tasks 7 and 9. `RenderOptions` fields identical in Tasks 9, 11, 12. `PosixRecorder.record(command, pre_commands, cast_path) -> Header` in Tasks 10 and 11. `check_self_contained` in Tasks 8 and 9. `KeyDecoder.feed(t, data)` in Tasks 4 and 7. `ANSI_NAMES` from Task 2 is imported by Task 8.
