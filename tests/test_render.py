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
