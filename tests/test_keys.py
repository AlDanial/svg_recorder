from svg_recorder.keys import KeyDecoder


def names(*chunks):
    d = KeyDecoder()
    out = []
    for t, data in chunks:
        out += d.feed(t, data)
    out += d.finish()
    return [n for _, n in out]


def test_printable_and_space():
    assert names((0, b"ab 1")) == ["a", "b", "<Space>", "1"]


def test_utf8_char_split_across_chunks():
    assert names((0, b"\xe4\xbd"), (0.01, b"\xa0")) == ["你"]


def test_control_letters_and_collisions():
    assert names((0, b"\x01\x18\x1a")) == ["<Ctrl>-a", "<Ctrl>-x", "<Ctrl>-z"]
    assert names((0, b"\x09\x0d\x0a\x7f\x08")) == [
        "<Tab>", "<Enter>", "<Enter>", "<Backspace>", "<Backspace>"]


def test_csi_and_ss3_keys():
    assert names((0, b"\x1b[A\x1b[B\x1b[C\x1b[D")) == [
        "<UpArrow>", "<DownArrow>", "<RightArrow>", "<LeftArrow>"]
    assert names((0, b"\x1b[5~\x1b[6~\x1b[H\x1b[F\x1b[2~\x1b[3~")) == [
        "<PgUp>", "<PgDn>", "<Home>", "<End>", "<Insert>", "<Delete>"]
    assert names((0, b"\x1bOP\x1b[15~\x1b[24~")) == ["<F1>", "<F5>", "<F12>"]


def test_csi_modifiers():
    assert names((0, b"\x1b[1;5A")) == ["<Ctrl>-<UpArrow>"]
    assert names((0, b"\x1b[3;3~")) == ["<Alt>-<Delete>"]


def test_alt_and_ctrl_alt():
    assert names((0, b"\x1bx")) == ["<Alt>-x"]
    assert names((0, b"\x1b\x02")) == ["<Ctrl>-<Alt>-b"]


def test_bare_escape_by_timeout_and_by_finish():
    assert names((0, b"\x1b"), (0.2, b"q")) == ["<Esc>", "q"]
    assert names((0, b"\x1b")) == ["<Esc>"]
    assert names((0, b"\x1b"), (0.01, b"[A")) == ["<UpArrow>"]


def test_timestamps_are_preserved():
    d = KeyDecoder()
    assert d.feed(1.5, b"a") == [(1.5, "a")]


def test_unknown_bytes_show_as_hex():
    assert names((0, b"\x1b[?99z")) == ["<0x1b>", "[", "?", "9", "9", "z"]
    assert names((0, b"\xff")) == ["<0xff>"]


def test_kitty_csi_u_valid():
    assert names((0, b"\x1b[97;5u")) == ["<Ctrl>-a"]


def test_kitty_csi_u_out_of_range():
    assert names((0, b"\x1b[9999999u")) == ["<0x1b>", "[", "9", "9", "9", "9", "9", "9", "9", "u"]
