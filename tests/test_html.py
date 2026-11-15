import re
from importlib.resources import files

from svg_recorder.html import SVG_MARKER, TITLE_MARKER, wrap_svg


def template() -> str:
    return files("svg_recorder").joinpath("player.html").read_text(encoding="utf-8")


def test_wrap_inserts_svg_once():
    page = wrap_svg("<svg>X</svg>", "a")
    assert page.count("<svg>X</svg>") == 1
    assert SVG_MARKER not in page and TITLE_MARKER not in page


def test_wrap_starts_with_doctype():
    # GitHub Pages only runs Jekyll on files that open with YAML front matter.
    page = wrap_svg("<svg/>", "a")
    assert page.startswith("<!DOCTYPE html>")
    assert '<meta charset="utf-8">' in page


def test_wrap_preserves_special_text():
    body = r"<svg>{{ x }} {% y %} \1 $& " + TITLE_MARKER + " " + SVG_MARKER + "</svg>"
    page = wrap_svg(body, "name")
    assert page.count(body) == 1


def test_wrap_escapes_title():
    page = wrap_svg("<svg/>", 'a<b>&"c')
    assert page.count("a&lt;b&gt;&amp;&quot;c") == 2  # <title> and the title bar
    assert 'a<b>&"c' not in page


def test_template_has_one_svg_slot_and_two_titles():
    t = template()
    assert t.count(SVG_MARKER) == 1
    assert t.count(TITLE_MARKER) == 2


def test_template_is_self_contained_and_classless():
    # The inlined SVG's stylesheet is document-wide (.b, .i, .u, .e, .fN, .gN,
    # .tN, text{...}), so the player markup must not use classes or <text>.
    t = template()
    for banned in ("class=", "<text", "src=", "url(", "@import", "@font-face", "//"):
        assert banned not in t, banned
    assert re.findall(r"""href=["'](?!#)""", t) == []
