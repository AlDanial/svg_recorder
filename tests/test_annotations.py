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
