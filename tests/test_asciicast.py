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
