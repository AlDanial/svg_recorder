from svg_recorder.patches import BLANK, blank_frame, diff_frames, is_blank, row_runs


def cell(ch, **kw):
    return BLANK._replace(char=ch, **kw)


def frame_from(lines, cols=None):
    cols = cols or max(len(l) for l in lines)
    return [[cell(ch) for ch in line.ljust(cols)] for line in lines]


def test_blank_frame_and_is_blank():
    f = blank_frame(3, 2)
    assert len(f) == 2 and len(f[0]) == 3 and f[1][2] == BLANK
    assert is_blank(BLANK) and is_blank(cell(""))
    assert not is_blank(cell("x"))
    assert not is_blank(cell(" ", bg="red"))
    assert not is_blank(cell(" ", reverse=True))


def test_row_runs_merges_small_gaps():
    old = frame_from(["abcdefghij"])[0]
    new = frame_from(["Xbcdefghij"])[0]
    assert row_runs(old, new, 2) == [(0, 1)]
    new = frame_from(["XbXdefXhiX"])[0]
    assert row_runs(old, new, 2) == [(0, 3), (6, 10)]
    assert row_runs(old, new, 0) == [(0, 1), (2, 3), (6, 7), (9, 10)]
    assert row_runs(old, old, 2) == []


def test_no_change_yields_nothing():
    f = frame_from(["hello", "world"])
    assert diff_frames(f, [list(r) for r in f]) == []


def test_single_character_patch():
    old = frame_from(["hello", "world"])
    new = frame_from(["hello", "wOrld"])
    [p] = diff_frames(old, new)
    assert (p.col, p.row, p.width, p.height) == (1, 1, 1, 1)
    assert p.rows == ((cell("O"),),)
    assert p.erase is True


def test_erase_false_when_old_region_blank():
    old = blank_frame(5, 2)
    new = frame_from(["     ", " ab  "])
    [p] = diff_frames(old, new)
    assert (p.col, p.row, p.width) == (1, 1, 2)
    assert p.erase is False


def test_stacked_runs_merge_into_rectangle():
    old = blank_frame(6, 4)
    new = frame_from(["      ", "  ab  ", "  cd  ", "      "])
    [p] = diff_frames(old, new)
    assert (p.col, p.row, p.width, p.height) == (2, 1, 2, 2)
    assert [c.char for c in p.rows[1]] == ["c", "d"]


def test_different_extents_stay_separate():
    old = blank_frame(6, 3)
    new = frame_from(["ab    ", "  cd  ", "  ef  "])
    ps = diff_frames(old, new)
    assert [(p.col, p.row, p.width, p.height) for p in ps] == [(0, 0, 2, 1), (2, 1, 2, 2)]


def test_whole_screen_when_over_threshold():
    old = frame_from(["aaaa", "aaaa"])
    new = frame_from(["bbbb", "bbba"])
    [p] = diff_frames(old, new, full_threshold=0.5)
    assert (p.col, p.row, p.width, p.height) == (0, 0, 4, 2)
    assert p.erase is True
    ps = diff_frames(old, new, full_threshold=1.0)
    assert [(p.col, p.row, p.width, p.height) for p in ps] == [(0, 0, 4, 1), (0, 1, 3, 1)]


def test_identical_row_objects_are_skipped():
    old = frame_from(["abc", "def"])
    new = [old[0], [cell("d"), cell("E"), cell("f")]]
    [p] = diff_frames(old, new)
    assert (p.col, p.row) == (1, 1)
