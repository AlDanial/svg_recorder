from svg_recorder.asciicast import Header
from svg_recorder.palette import KITTY_DEFAULT
from svg_recorder.patches import BLANK
from svg_recorder.screen import Footer, Sampler

COLORS = ("#303030", "#f0f0f0")


def text(row):
    return "".join(c.char for c in row)


def test_footer_shows_last_five_keys_newest_bold():
    f = Footer(30, COLORS)
    for i, k in enumerate("abcdefg"):
        f.push_key(i * 0.1, k)
    [row] = f.rows(0.7)
    assert text(row).rstrip() == "c d e f g"
    assert row[8].bold is True and row[8].char == "g"
    assert row[6].bold is False
    assert row[0].fg == "#f0f0f0" and row[0].bg == "#303030" and row[29].bg == "#303030"


def test_footer_bold_reverts_after_two_seconds():
    f = Footer(20, COLORS)
    f.push_key(1.0, "x")
    assert f.rows(2.9)[0][0].bold is True
    assert f.rows(3.05)[0][0].bold is False


def test_footer_truncates_to_width():
    f = Footer(4, COLORS)
    for k in ["<PgUp>", "<PgDn>"]:
        f.push_key(0, k)
    [row] = f.rows(0)
    assert len(row) == 4




def sampler(events, w=10, h=2, **kw):
    return Sampler(Header(w, h, 0, KITTY_DEFAULT), events, **kw)


def test_sampler_ticks_and_feeds_output():
    events = [(0.0, "o", b"ab"), (0.12, "o", b"\x1b[31mc")]
    frames = list(sampler(events, time_delta=0.05).frames())
    times = [t for t, _ in frames]
    assert times[:3] == [0.0, 0.05, 0.1]
    assert times[-1] >= 0.12
    assert text(frames[0][1][0]).rstrip() == "ab"
    last = frames[-1][1]
    assert text(last[0]).rstrip() == "abc" and last[0][2].fg == "red"
    assert last[1][0] == BLANK


def test_sampler_keeps_row_identity_when_unchanged():
    events = [(0.0, "o", b"ab"), (0.1, "o", b"\x1b[2;1Hzz")]
    frames = list(sampler(events).frames())
    assert frames[1][1][0] is frames[0][1][0]
    assert frames[-1][1][0] is frames[0][1][0]
    assert frames[-1][1][1] is not frames[0][1][1]


def test_sampler_cursor_marks_cell_reverse():
    events = [(0.0, "o", b"ab")]
    frames = list(sampler(events, cursor=True).frames())
    row = frames[-1][1][0]
    assert row[2].reverse is True and row[1].reverse is False
    frames = list(sampler([(0.0, "o", b"ab\x1b[?25l")], cursor=True).frames())
    assert frames[-1][1][0][2].reverse is False


def test_sampler_cursor_row_keeps_identity_when_static():
    events = [(0.0, "o", b"ab"), (0.3, "o", b"")]
    frames = list(sampler(events, cursor=True).frames())
    assert frames[1][1][0] is frames[0][1][0]
    assert frames[-1][1][0] is frames[0][1][0]

    events = [(0.0, "o", b"ab"), (0.3, "o", b"c")]
    frames = list(sampler(events, cursor=True).frames())
    row0, row_last = frames[0][1][0], frames[-1][1][0]
    assert row_last is not row0
    assert row_last[2].char == "c" and row_last[2].reverse is False
    assert row_last[3].reverse is True


def test_sampler_wide_char_continuation_cell_is_empty():
    frames = list(sampler([(0.0, "o", "你a".encode())]).frames())
    row = frames[-1][1][0]
    assert row[0].char == "你" and row[1].char == "" and row[2].char == "a"


def test_sampler_footer_rows_appended_and_keys_fed():
    f = Footer(10, COLORS)
    events = [(0.0, "o", b"x"), (0.02, "i", b"\x1b[A"), (0.3, "o", b"y")]
    frames = list(sampler(events, h=1, footer=f).frames())
    assert len(frames[0][1]) == 2
    assert text(frames[-1][1][1]).rstrip() == "<UpArrow>"


def test_footer_pending_until_tracks_bold_deadline():
    f = Footer(20, COLORS)
    assert f.pending_until() is None
    f.push_key(1.0, "x")
    assert f.pending_until() == 3.0


def test_sampler_keeps_ticking_until_footer_bold_reverts():
    f = Footer(10, COLORS)
    events = [(0.0, "o", b"x"), (0.5, "i", b"q")]
    frames = list(sampler(events, h=1, footer=f).frames())
    t, frame = frames[-1]
    assert t >= 2.5
    row = frame[1]
    assert text(row).rstrip() == "q"
    assert row[0].bold is False
    # the key is still bold while the hold has not elapsed
    bold_at = [ft for ft, fr in frames if fr[1][0].bold]
    assert bold_at and max(bold_at) < 2.5


def test_sampler_flushes_trailing_escape_through_decoder_finish():
    f = Footer(10, COLORS)
    events = [(0.0, "o", b"x"), (0.3, "i", b"\x1b")]
    frames = list(sampler(events, h=1, footer=f).frames())
    assert text(frames[-1][1][1]).rstrip() == "<Esc>"
