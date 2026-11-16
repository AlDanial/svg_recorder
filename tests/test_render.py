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
    assert ">q</text>" in svg
    assert "#303030" in svg


def test_render_cast(tmp_path):
    p = tmp_path / "r.cast"
    with Writer(p, HEADER) as w:
        w.write(0.0, "o", b"abc")
    svg = render_cast(p, RenderOptions(loop=False))
    assert ">abc</text>" in svg and "infinite" not in svg


def test_render_duration_covers_footer_bold_revert():
    import re
    events = [(0.0, "o", b"x"), (0.5, "i", b"q")]
    svg = render_events(HEADER, events, RenderOptions(footer=True, hold=2.0))
    duration = float(re.search(r"animation:a\d+ ([\d.]+)s", svg).group(1))
    pcts = [float(p) for p in re.findall(r"0%\{visibility:hidden\}([\d.]+)%", svg)]
    assert pcts, svg
    assert max(pcts) / 100.0 * duration >= 2.5


def _times(events):
    return [t for t, _, _ in events]


def test_compress_time_caps_pauses_before_keys_and_shifts_what_follows():
    from svg_recorder.render import compress_time
    events = [(0.0, "o", b"$ "), (0.1, "i", b"l"), (0.11, "o", b"l"),
              (1.11, "i", b"s"), (1.12, "o", b"s"), (1.15, "i", b"\r"), (4.15, "o", b"out")]
    out = compress_time(events, 0.2)
    #        prompt key  echo  key (1.0 -> 0.2)  echo  key (short)  output (3.0 kept)
    assert _times(out) == [0.0, 0.1, 0.11, 0.31, 0.32, 0.35, 3.35]
    assert [e[1:] for e in out] == [e[1:] for e in events]


def test_compress_time_caps_the_wait_between_the_first_two_frames():
    from svg_recorder.render import compress_time
    slow_start = [(0.5, "o", b"a"), (3.5, "o", b"b"), (6.5, "o", b"c")]
    assert _times(compress_time(slow_start, 1.0)) == [0.5, 1.5, 4.5]   # only the first wait
    typed = [(0.0, "o", b"$ "), (5.0, "i", b"x"), (5.01, "o", b"x")]
    assert _times(compress_time(typed, 0.25)) == [0.0, 0.25, 0.26]     # not cut twice


def test_compress_time_leaves_short_pauses_and_output_waits_alone():
    from svg_recorder.render import compress_time
    events = [(0.0, "o", b"a"), (0.1, "o", b"b"), (0.2, "i", b"k"), (9.0, "o", b"done")]
    assert compress_time(events, 0.5) == events
    assert compress_time([], 0.5) == []


def test_compress_time_keeps_a_bare_escape_apart_from_the_next_key():
    from svg_recorder.keys import ESC_TIMEOUT, KeyDecoder
    from svg_recorder.render import compress_time
    events = [(0.0, "o", b"x"), (1.0, "i", b"\x1b"), (3.0, "i", b"j")]
    out = compress_time(events, 0.01)
    assert out[2][0] - out[1][0] > ESC_TIMEOUT
    decoder = KeyDecoder()
    names = [n for t, _, d in out[1:] for _, n in decoder.feed(t, d)]
    assert names == ["<Esc>", "j"]
    # An escape sequence that arrived in pieces is not pulled apart.
    arrow = [(0.0, "o", b"x"), (1.0, "i", b"\x1b"), (1.001, "i", b"[A")]
    assert compress_time(arrow, 0.01) == [(0.0, "o", b"x"), (0.01, "i", b"\x1b"), (0.011, "i", b"[A")]


def test_render_time_compress_shortens_the_animation():
    import re
    events = [(0.0, "o", b"$ "), (2.0, "i", b"l"), (2.01, "o", b"l"), (5.0, "i", b"s"), (5.01, "o", b"s")]

    def duration(opts):
        return float(re.search(r"animation:a\d+ ([\d.]+)s", render_events(HEADER, events, opts)).group(1))

    assert duration(RenderOptions()) == 7.05             # last frame on the 5.05 tick, plus the 2 s hold
    assert duration(RenderOptions(time_compress=0.5)) == 3.05
    assert events[3][0] == 5.0                                           # the caller's events are untouched
