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
