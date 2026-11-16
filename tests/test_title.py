from svg_recorder.title import MARK, TitleFilter, begin, end

M = MARK.encode()


def test_begin_saves_the_title_then_shows_the_marker():
    assert begin() == b"\x1b[22;0t\x1b]2;" + M + b"\x07"


def test_end_clears_the_marker_then_restores_the_saved_title():
    assert end() == b"\x1b]2;\x07\x1b[23;0t"


def test_plain_output_passes_through_untouched():
    assert TitleFilter().feed(b"hello \x1b[31mworld\r\n") == b"hello \x1b[31mworld\r\n"


def test_title_sequences_keep_the_marker_in_front():
    f = TitleFilter()
    assert f.feed(b"a\x1b]0;me@host: ~\x07b") == b"a\x1b]0;" + M + b" | me@host: ~\x07b"
    assert f.feed(b"\x1b]2;vim\x1b\\") == b"\x1b]2;" + M + b" | vim\x1b\\"


def test_an_empty_title_becomes_the_bare_marker():
    assert TitleFilter().feed(b"\x1b]2;\x07") == b"\x1b]2;" + M + b"\x07"


def test_other_osc_sequences_are_left_alone():
    data = b"\x1b]1;icon\x07\x1b]11;?\x1b\\\x1b]8;;http://x\x07link\x1b]8;;\x07"
    assert TitleFilter().feed(data) == data


def test_a_title_split_across_chunks_is_rewritten_once_complete():
    whole = b"x\x1b]0;long title\x07y"
    want = b"x\x1b]0;" + M + b" | long title\x07y"
    for cut in range(1, len(whole)):
        f = TitleFilter()
        assert f.feed(whole[:cut]) + f.feed(whole[cut:]) + f.flush() == want, cut


def test_a_trailing_escape_is_held_only_until_the_next_chunk():
    f = TitleFilter()
    assert f.feed(b"ab\x1b") == b"ab"
    assert f.feed(b"[1mc") == b"\x1b[1mc"


def test_flush_releases_an_unterminated_sequence():
    f = TitleFilter()
    assert f.feed(b"a\x1b]0;never ends") == b"a"
    assert f.flush() == b"\x1b]0;never ends"
    assert f.flush() == b""


def test_an_overlong_unterminated_sequence_is_not_held_forever():
    f = TitleFilter()
    data = b"\x1b]0;" + b"x" * 5000
    assert f.feed(data) == data
