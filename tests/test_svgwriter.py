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


def test_multi_row_patch_emits_one_text_per_row():
    w = SvgWriter(KITTY_DEFAULT, 10, 3)
    w.add_frame(0.0, [patch(1, 0, ["ab", "cd"])])
    svg = w.to_string()
    assert ('<text x="8" y="13" textLength="16">ab</text>'
            '<text x="8" y="30" textLength="16">cd</text>') in svg


def test_every_run_is_its_own_text_element():
    # Firefox ignores textLength on <tspan>, so a run inside a shared <text>
    # is laid out at the font's natural advance and pushes every later run on
    # the row sideways.  Each run is pinned to its cells by its own <text>.
    w = SvgWriter(KITTY_DEFAULT, 10, 2)
    rows = ((cell("a"), cell("b"), cell("c", fg="red"), cell("d", fg="red"), cell("e")),)
    w.add_frame(0.0, [Patch(1, 0, 5, rows, False)])
    svg = w.to_string()
    assert "<tspan" not in svg
    assert '<text x="8" y="13" textLength="16">ab</text>' in svg
    assert re.search(r'<text x="24" y="13" textLength="16" class="f\d+">cd</text>', svg)
    assert '<text x="40" y="13" textLength="8">e</text>' in svg


def test_blank_runs_emit_no_text_unless_underlined():
    w = SvgWriter(KITTY_DEFAULT, 10, 2)
    rows = ((cell("a"), cell(" ", fg="red"), cell(" ", fg="red"), cell("b")),)
    w.add_frame(0.0, [Patch(0, 0, 4, rows, False)])
    svg = w.to_string()
    assert svg.count("<text") == 2
    assert '<text x="24" y="13" textLength="8">b</text>' in svg

    w = SvgWriter(KITTY_DEFAULT, 10, 2)
    rows = ((cell("a"), cell(" ", underline=True), cell(" ", underline=True), cell("b")),)
    w.add_frame(0.0, [Patch(0, 0, 4, rows, False)])
    assert '<text x="8" y="13" textLength="16" class="u">  </text>' in w.to_string()


def test_middle_blank_row_does_not_shift_later_rows():
    # A middle row made only of continuation cells (char == "") emits no text
    # at all; absolute y on every later row keeps them in place.
    w = SvgWriter(KITTY_DEFAULT, 10, 4)
    w.add_frame(0.0, [Patch(0, 0, 1, ((cell("a"),), (cell(""),), (cell("b"),)), False)])
    svg = w.to_string()
    assert '<text x="0" y="47" textLength="8">b</text>' in svg
    assert svg.count("<text") == 2          # the empty middle row is skipped
    assert "></text>" not in svg


def test_row_starting_with_continuation_cell_shifts_x():
    # The leading continuation cell carries no text, so its width folds into
    # the x of the run that does.
    w = SvgWriter(KITTY_DEFAULT, 10, 2)
    w.add_frame(0.0, [Patch(0, 0, 3, ((cell(""), cell("a", fg="red"), cell("b", fg="red")),), False)])
    svg = w.to_string()
    assert "></text>" not in svg
    assert re.search(r'<text x="8" y="13" textLength="16" class="f\d+">ab</text>', svg)

    # ... and the same for a later row, which carries its own x.
    w = SvgWriter(KITTY_DEFAULT, 10, 3)
    w.add_frame(0.0, [Patch(1, 0, 2,
                            ((cell("a"), cell("b")),
                             (cell(""), cell("c", fg="red"))), False)])
    svg = w.to_string()
    assert "></text>" not in svg
    assert re.search(r'<text x="16" y="30" textLength="8" class="f\d+">c</text>', svg)


def test_fully_empty_row_patch_emits_no_text():
    w = SvgWriter(KITTY_DEFAULT, 10, 2)
    w.add_frame(0.0, [Patch(0, 0, 1, ((cell(""),),), True)])
    svg = w.to_string()
    assert "<text" not in svg
    assert 'class="e"' in svg          # the erase rect is still emitted

    # nothing to draw at all: no element, and no timing class for it either
    w = SvgWriter(KITTY_DEFAULT, 10, 2)
    w.add_frame(1.0, [Patch(0, 0, 1, ((cell(""),),), False)])
    svg = w.to_string()
    assert "<text" not in svg and "<use" not in svg and "<g " not in svg
    assert "@keyframes" not in svg


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
    assert re.search(r'<text x="0" y="13" textLength="24" class="f\d+ b">ab</text>', svg) is None
    assert re.search(r'<text x="0" y="13" textLength="16" class="f\d+ b">ab</text>'
                     r'<text x="16" y="13" textLength="8">c</text>', svg)


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
    assert '[class^=t]{visibility:hidden;animation:s 1ms steps(1,start) forwards}' in svg
    assert '@keyframes s{to{visibility:visible}}' in svg
    assert '.t1{animation-delay:1.25s}' in svg
    assert 'infinite' not in svg


def test_duration_clamped_against_zero_and_short_values():
    w = SvgWriter(KITTY_DEFAULT, 10, 2, loop=True)
    w.add_frame(0.0, [patch(0, 0, ["a"])])
    w.add_frame(1.0, [patch(0, 0, ["b"])])
    svg = w.to_string(duration=0)  # must not raise ZeroDivisionError
    assert svg
    svg2 = w.to_string(duration=0.5)  # shorter than last frame time
    assert '@keyframes a1{0%{visibility:hidden}100%{visibility:visible}}' in svg2
    assert '200%' not in svg2


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
