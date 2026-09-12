import json

import pytest

from svg_recorder.asciicast import CastError, Header, Writer, read
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


def write_cast(tmp_path, text):
    path = tmp_path / "bad.cast"
    path.write_text(text, encoding="utf-8")
    return path


def test_non_json_header_raises_cast_error(tmp_path, capsys):
    path = write_cast(tmp_path, "<svg>\n")
    with pytest.raises(CastError) as e:
        read(path)
    assert "line 1" in str(e.value) and "bad.cast" in str(e.value)


def test_header_without_width_raises_cast_error(tmp_path):
    path = write_cast(tmp_path, '{"version": 2, "height": 5}\n')
    with pytest.raises(CastError) as e:
        read(path)
    assert "line 1" in str(e.value) and "width" in str(e.value)


def test_bad_theme_raises_cast_error(tmp_path):
    path = write_cast(tmp_path, '{"version": 2, "width": 5, "height": 5, "theme": {"fg": "#fff"}}\n')
    with pytest.raises(CastError) as e:
        read(path)
    assert "line 1" in str(e.value)


def test_bad_event_line_names_its_line_number(tmp_path):
    good = '{"version": 2, "width": 5, "height": 5}\n'
    with pytest.raises(CastError) as e:
        read(write_cast(tmp_path, good + '[0.0, "o", "a"]\n' + "not json\n"))
    assert "line 3" in str(e.value)
    with pytest.raises(CastError) as e:
        read(write_cast(tmp_path, good + '{"t": 1}\n'))
    assert "line 2" in str(e.value)
    with pytest.raises(CastError) as e:
        read(write_cast(tmp_path, good + '[0.0, "o"]\n'))
    assert "line 2" in str(e.value)
    with pytest.raises(CastError) as e:
        read(write_cast(tmp_path, good + '[0.0, "o", 5]\n'))
    assert "line 2" in str(e.value)


def test_cast_error_is_a_value_error():
    assert issubclass(CastError, ValueError)
