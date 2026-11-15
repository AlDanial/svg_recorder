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
    assert p.resolve("", "#000000") == "#000000"
    assert p.resolve("12", "#000000") == "#000000"


def test_resolve_maps_every_pyte_colour_name():
    # pyte emits aixterm names for SGR 90-97, including two misspelled ones;
    # none of them may leak through as a bare CSS keyword.
    import pyte.graphics as g
    names = set(g.FG.values()) | set(g.BG.values()) | set(g.FG_AIXTERM.values()) | set(g.BG_AIXTERM.values())
    for name in names - {"default"}:
        assert KITTY_DEFAULT.resolve(name, "#123456") in KITTY_DEFAULT.colors, name


def test_resolve_passes_css_colours_through():
    p = KITTY_DEFAULT
    assert p.resolve("#333", "#000000") == "#333"
    assert p.resolve("#ABC", "#000000") == "#abc"
    assert p.resolve("navy", "#000000") == "navy"
    assert p.resolve("rgb(1,2,3)", "#000000") == "rgb(1,2,3)"
    assert p.resolve("rgb(1, 2, 3)", "#000000") == "rgb(1, 2, 3)"
    assert p.resolve("hsl(10deg 20% 30% / 40%)", "#000000") == "hsl(10deg 20% 30% / 40%)"
    assert p.resolve("rebeccapurple", "#000000") == "rebeccapurple"


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


def test_from_theme_rejects_values_that_are_not_colours():
    # Theme values come from a .cast file, which may be someone else's, and
    # are written into the SVG (and the --html page) unescaped.
    import pytest
    evil = '"/><script>alert(1)</script>'
    theme = KITTY_DEFAULT.to_theme()
    assert Palette.from_theme({**theme, "bg": "#fdf6e3"}).bg == "#fdf6e3"
    for bad in ({**theme, "fg": evil}, {**theme, "bg": 'rgb("/><script>)'},
                {**theme, "palette": ":".join([evil] + list(KITTY_DEFAULT.colors[1:]))},
                {**theme, "palette": "#000000:#ffffff"}):
        with pytest.raises(ValueError):
            Palette.from_theme(bad)


def test_resolve_rejects_malformed_hash_values():
    assert KITTY_DEFAULT.resolve('#"/><script>', "#123456") == "#123456"
    assert KITTY_DEFAULT.resolve("#333", "#123456") == "#333"
