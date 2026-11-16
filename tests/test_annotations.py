import re

import pytest

from svg_recorder.annotations import (AnnotationError, SvgError, annotate_svg, load_annotations,
                                      loop_duration, parse_annotations, parse_time)
from svg_recorder.asciicast import Header
from svg_recorder.palette import KITTY_DEFAULT
from svg_recorder.render import RenderOptions, render_events
from svg_recorder.svgwriter import check_self_contained

HEADER = Header(20, 3, 0, KITTY_DEFAULT)                      # 160 x 51 px
EVENTS = [(0.0, "o", b"hello"), (8.0, "o", b"\r\nbye")]       # loops every 10 s


def svg(**opts):
    return render_events(HEADER, EVENTS, RenderOptions(**opts))


def test_parse_time_accepts_minutes_seconds_and_fractions():
    assert parse_time("0:00") == 0.0
    assert parse_time("1:03") == 63.0
    assert parse_time("2:59.5") == 179.5
    assert parse_time("0:01.1") == pytest.approx(1.1)
    assert parse_time("0.00") == 0.0                          # plain seconds
    assert parse_time("12.5") == 12.5
    for bad in ("", "abc", "1:", ":5", "1:2:3", "-1", "1:x", "Hello"):
        assert parse_time(bad) is None, bad


def test_parse_annotations_reads_time_then_text():
    notes = parse_annotations("0:01.1  Hello\n0:05.5\twelcome to this  recording\n\n# comment\n0:09\n")
    assert notes == [(pytest.approx(1.1), "Hello"), (5.5, "welcome to this  recording"), (9.0, "")]


def test_parse_annotations_sorts_by_time():
    assert parse_annotations("0:05 b\n0:01 a\n0:05 c\n") == [(1.0, "a"), (5.0, "b"), (5.0, "c")]


def test_parse_annotations_reports_the_bad_line():
    with pytest.raises(AnnotationError) as info:
        parse_annotations("0:01 fine\nHello there\n")
    assert info.value.line_no == 2 and "line 2" in str(info.value) and "'Hello'" in str(info.value)


def test_load_annotations(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("0:02 héllo\n", encoding="utf-8")
    assert load_annotations(p) == [(2.0, "héllo")]


def test_footer_row_is_added_below_the_svg():
    out = annotate_svg(svg(), [(1.1, "Hello")])
    assert 'width="160" height="68" viewBox="0 0 160 68"' in out      # 51 + one 17 px row
    assert '<rect x="0" y="51" width="160" height="17" style="fill:#303030"/>' in out
    assert '<text x="0" y="64" textLength="40" style="fill:#f0f0f0">Hello</text>' in out
    assert out.endswith("</svg>") and out.count("<svg") == 1 and out.count("</style>") == 1
    assert check_self_contained(out) == []


def test_notes_appear_at_their_times_in_a_looping_svg():
    src = svg()
    assert loop_duration(src) == 10.0
    out = annotate_svg(src, [(1.1, "Hello"), (5.5, "welcome")])
    assert ".n1{animation:n1 10s steps(1,end) infinite}@keyframes n1{0%{visibility:hidden}11%{visibility:visible}}" in out
    assert "@keyframes n2{0%{visibility:hidden}55%{visibility:visible}}" in out
    # Each note repaints the footer, so the later one covers the earlier one.
    first, second = out.index('<g class="n1">'), out.index('<g class="n2">')
    assert first < second
    assert out[first:second].count("<rect") == 1 and ">Hello</text>" in out[first:second]
    # Before the first note the footer is the bare background.
    assert out.index('y="51" width="160" height="17"') < first


def test_notes_use_delays_in_a_play_once_svg():
    src = svg(loop=False)
    assert loop_duration(src) is None
    out = annotate_svg(src, [(1.5, "Hello"), (25.0, "after the end is fine here")])
    assert ".n1{visibility:hidden;animation:n1 1ms steps(1,start) 1.5s forwards}@keyframes n1{to{visibility:visible}}" in out
    assert "steps(1,start) 25s forwards" in out


def test_a_note_at_time_zero_is_visible_from_the_start():
    out = annotate_svg(svg(), [(0.0, "intro")])
    assert ">intro</text>" in out and "n1" not in out


def test_a_note_without_text_blanks_the_footer():
    out = annotate_svg(svg(), [(1.0, "Hello"), (2.0, "")])
    assert re.search(r'<g class="n2"><rect [^>]*/></g></svg>$', out)


def test_notes_past_the_end_of_the_loop_are_left_out():
    out = annotate_svg(svg(), [(1.0, "seen"), (10.0, "never"), (12.0, "nor this")])
    assert "seen" in out and "never" not in out and "nor this" not in out


def test_long_notes_wrap_onto_more_footer_rows():
    out = annotate_svg(svg(), [(1.0, "short"), (2.0, "this note is much wider than twenty columns")])
    assert 'height="102"' in out                                       # 51 + three rows
    assert 'y="51" width="160" height="51"' in out
    lines = re.findall(r'<text x="0" y="(\d+)" textLength="(\d+)" style[^>]*>([^<]*)</text>', out)
    assert lines == [("64", "40", "short"), ("64", "136", "this note is much"),
                     ("81", "136", "wider than twenty"), ("98", "56", "columns")]


def test_text_and_colors_are_escaped():
    out = annotate_svg(svg(), [(1.0, "a <b> & `c`")], colors=('red"x', "#fff"))
    assert ">a &lt;b&gt; &amp; `c`</text>" in out
    assert 'style="fill:red&quot;x"' in out


def test_annotating_twice_stacks_a_second_footer():
    once = annotate_svg(svg(footer=True), [(1.0, "first")])            # key footer already there: 68 px
    assert 'height="85"' in once
    twice = annotate_svg(once, [(2.0, "second"), (3.0, "third")])
    assert 'height="102" viewBox="0 0 160 102"' in twice
    assert twice.count(".n1{") == 1 and ".n2{" in twice and ".n3{" in twice
    assert '<g class="n1"><rect x="0" y="68"' in twice and '<g class="n2"><rect x="0" y="85"' in twice
    assert twice.count("</style>") == 1


def test_an_svg_without_a_style_element_gets_one():
    plain = '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="17" viewBox="0 0 80 17"><rect/></svg>'
    out = annotate_svg(plain, [(1.0, "x")])
    assert out.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="34" viewBox="0 0 80 34"><style>.n1{')


def test_text_that_is_not_a_sized_svg_is_rejected():
    for bad in ("hello", "<svg><rect/></svg>", '<svg width="100%" height="5" viewBox="0 0 1 1"></svg>',
                '<svg width="10" height="5"></svg>'):
        with pytest.raises(SvgError):
            annotate_svg(bad, [(1.0, "x")])


def test_parse_annotations_ignores_indentation_blank_lines_and_comments():
    text = ("# a comment\n"
            "   0:01 indented with spaces\n"
            "\n"
            "   \t \n"
            "\t0:02\tindented with a tab\n"
            "   # an indented comment\n"
            "\t#0:03 commented out\n"
            "0:04 a # inside the text is kept\n")
    assert parse_annotations(text) == [(1.0, "indented with spaces"), (2.0, "indented with a tab"),
                                       (4.0, "a # inside the text is kept")]
