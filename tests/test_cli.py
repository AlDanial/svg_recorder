import gzip
import tempfile
from datetime import datetime

import pytest

from svg_recorder import cli
from svg_recorder.asciicast import Header, Writer
from svg_recorder.palette import KITTY_DEFAULT


def make_cast(path, width=10):
    with Writer(path, Header(width, 2, 0, KITTY_DEFAULT)) as w:
        w.write(0.0, "o", b"hi")
        w.write(0.3, "i", b"k")
    return path


def test_default_output_name():
    assert cli.default_output_name(datetime(2026, 9, 11, 8, 5, 9)) == "recording-2026-09-11-08-05-09.svg"


def test_render_subcommand_writes_svg(tmp_path):
    cast = make_cast(tmp_path / "a.cast")
    out = tmp_path / "a.svg"
    assert cli.main(["render", str(cast), "-o", str(out), "--no-loop", "-t", "0.1"]) == 0
    svg = out.read_text()
    assert ">hi</text>" in svg and "infinite" not in svg


def test_render_footer_options(tmp_path):
    cast = make_cast(tmp_path / "a.cast", width=20)
    out = tmp_path / "a.svg"
    rc = cli.main(["render", str(cast), "-o", str(out), "-f", "--footer-colors", "#111111", "#eeeeee"])
    assert rc == 0
    svg = out.read_text()
    assert ">k</text>" in svg and "#111111" in svg


def test_gzip_output(tmp_path):
    cast = make_cast(tmp_path / "a.cast")
    out = tmp_path / "a.svgz"
    assert cli.main(["render", str(cast), "-o", str(out), "--gzip"]) == 0
    assert b"<svg" in gzip.decompress(out.read_bytes())


def test_gzip_rewrites_svg_suffix_to_svgz(tmp_path, capsys):
    cast = make_cast(tmp_path / "a.cast")
    assert cli.main(["render", str(cast), "-o", str(tmp_path / "a.svg"), "--gzip"]) == 0
    assert not (tmp_path / "a.svg").exists()
    assert b"<svg" in gzip.decompress((tmp_path / "a.svgz").read_bytes())
    assert "a.svgz" in capsys.readouterr().err


def test_default_output_name_gzip():
    assert cli.default_output_name(datetime(2026, 9, 11, 8, 5, 9), gzip=True) == \
        "recording-2026-09-11-08-05-09.svgz"


def test_record_flow_gzip_uses_svgz(tmp_path, monkeypatch):
    class FakeRecorder:
        def record(self, command, pre_commands, cast_path):
            make_cast(cast_path)
            return Header(10, 2, 0, KITTY_DEFAULT)

    monkeypatch.setattr(cli, "get_recorder", lambda: FakeRecorder())
    assert cli.main(["-o", str(tmp_path / "s.svg"), "--gzip", "--keep-recording"]) == 0
    assert (tmp_path / "s.svgz").exists() and not (tmp_path / "s.svg").exists()
    assert (tmp_path / "s.cast").exists()


def test_missing_pre_commands_file_fails(tmp_path, capsys):
    rc = cli.main(["-F", str(tmp_path / "nope.txt"), "true"])
    assert rc == 2
    assert "nope.txt" in capsys.readouterr().err


def test_read_pre_commands_merges_file_then_string(tmp_path):
    f = tmp_path / "pre.txt"
    f.write_text("# c\ncd /tmp\n\nexport A=1\n")
    rec_parser, _ = cli.build_parsers()
    args = rec_parser.parse_args(["-F", str(f), "-c", "export B=2; export C=3"])
    assert cli.read_pre_commands(args) == ["cd /tmp", "export A=1", "export B=2", "export C=3"]


def test_record_flow_uses_recorder_and_keeps_cast(tmp_path, monkeypatch):
    calls = {}

    class FakeRecorder:
        def record(self, command, pre_commands, cast_path):
            calls["command"] = command
            calls["pre"] = pre_commands
            make_cast(cast_path)
            return Header(10, 2, 0, KITTY_DEFAULT)

    monkeypatch.setattr(cli, "get_recorder", lambda: FakeRecorder())
    out = tmp_path / "s.svg"
    rc = cli.main(["-o", str(out), "--keep-recording", "-c", "export X=1", "some command"])
    assert rc == 0
    assert calls == {"command": "some command", "pre": ["export X=1"]}
    assert out.exists() and (tmp_path / "s.cast").exists()


def test_record_flow_discards_cast_by_default(tmp_path, monkeypatch):
    class FakeRecorder:
        def record(self, command, pre_commands, cast_path):
            make_cast(cast_path)
            return Header(10, 2, 0, KITTY_DEFAULT)

    monkeypatch.setattr(cli, "get_recorder", lambda: FakeRecorder())
    out = tmp_path / "s.svg"
    assert cli.main(["-o", str(out)]) == 0
    assert out.exists() and not (tmp_path / "s.cast").exists()


def test_render_output_dir_missing_fails(tmp_path, capsys):
    cast = make_cast(tmp_path / "a.cast")
    out = tmp_path / "nodir" / "a.svg"
    rc = cli.main(["render", str(cast), "-o", str(out)])
    assert rc == 2
    err = capsys.readouterr().err
    assert err.startswith("svg_recorder:")
    assert not out.exists()


def test_record_flow_output_dir_missing_cleans_up_temp_cast(tmp_path, monkeypatch, capsys):
    class FakeRecorder:
        def record(self, command, pre_commands, cast_path):
            make_cast(cast_path)
            return Header(10, 2, 0, KITTY_DEFAULT)

    monkeypatch.setattr(cli, "get_recorder", lambda: FakeRecorder())

    real_ntf = tempfile.NamedTemporaryFile

    def fake_ntf(*args, **kwargs):
        kwargs["dir"] = str(tmp_path)
        return real_ntf(*args, **kwargs)

    monkeypatch.setattr(cli.tempfile, "NamedTemporaryFile", fake_ntf)

    out = tmp_path / "nodir" / "s.svg"
    rc = cli.main(["-o", str(out)])
    assert rc == 2
    err = capsys.readouterr().err
    assert err.startswith("svg_recorder:")
    assert not out.exists()
    assert list(tmp_path.glob("*.cast")) == []


def test_footer_colors_accept_any_css_color(tmp_path):
    cast = make_cast(tmp_path / "a.cast", width=20)
    out = tmp_path / "a.svg"
    rc = cli.main(["render", str(cast), "-o", str(out), "-f", "--footer-colors", "#333", "navy"])
    assert rc == 0
    style = out.read_text().split("<style>")[1].split("</style>")[0]
    assert "fill:#333}" in style
    assert "fill:navy}" in style


def test_render_of_non_cast_file_fails_cleanly(tmp_path, capsys):
    bad = tmp_path / "a.cast"
    bad.write_text("<svg>\n")
    rc = cli.main(["render", str(bad), "-o", str(tmp_path / "a.svg")])
    assert rc == 2
    err = capsys.readouterr().err
    assert err.startswith("svg_recorder:") and "line 1" in err


def test_record_flow_bad_cast_fails_cleanly(tmp_path, monkeypatch, capsys):
    class FakeRecorder:
        def record(self, command, pre_commands, cast_path):
            cast_path.write_text("<svg>\n")
            return Header(10, 2, 0, KITTY_DEFAULT)

    monkeypatch.setattr(cli, "get_recorder", lambda: FakeRecorder())
    rc = cli.main(["-o", str(tmp_path / "s.svg"), "--keep-recording"])
    assert rc == 2
    assert capsys.readouterr().err.startswith("svg_recorder:")


def test_html_render_writes_page_next_to_svg(tmp_path, capsys):
    cast = make_cast(tmp_path / "a.cast")
    out = tmp_path / "a.svg"
    assert cli.main(["render", str(cast), "-o", str(out), "--html"]) == 0
    page = (tmp_path / "a.html").read_text(encoding="utf-8")
    assert out.read_text() in page and ">hi</text>" in page
    assert "<title>a</title>" in page
    err = capsys.readouterr().err
    assert "a.svg" in err and "a.html" in err


def test_html_with_gzip_embeds_plain_svg(tmp_path):
    cast = make_cast(tmp_path / "a.cast")
    assert cli.main(["render", str(cast), "-o", str(tmp_path / "a.svg"), "--gzip", "--html"]) == 0
    assert b"<svg" in gzip.decompress((tmp_path / "a.svgz").read_bytes())
    assert ">hi</text>" in (tmp_path / "a.html").read_text(encoding="utf-8")


def test_html_name_replaces_only_the_last_suffix(tmp_path):
    cast = make_cast(tmp_path / "a.cast")
    assert cli.main(["render", str(cast), "-o", str(tmp_path / "out"), "--html"]) == 0
    assert (tmp_path / "out.html").exists()
    assert cli.main(["render", str(cast), "-o", str(tmp_path / "a.b.svg"), "--html"]) == 0
    assert (tmp_path / "a.b.html").exists()


def test_html_refuses_html_output_name(tmp_path, capsys):
    cast = make_cast(tmp_path / "a.cast")
    out = tmp_path / "a.html"
    assert cli.main(["render", str(cast), "-o", str(out), "--html"]) == 2
    assert "--html" in capsys.readouterr().err
    assert not out.exists()


def test_html_refuses_html_output_name_before_recording(tmp_path, monkeypatch, capsys):
    def no_recorder():
        raise AssertionError("recording started")

    monkeypatch.setattr(cli, "get_recorder", no_recorder)
    assert cli.main(["-o", str(tmp_path / "A.HTML"), "--html"]) == 2
    assert "--html" in capsys.readouterr().err


def test_html_record_path(tmp_path, monkeypatch, capsys):
    class FakeRecorder:
        def record(self, command, pre_commands, cast_path):
            make_cast(cast_path)
            return Header(10, 2, 0, KITTY_DEFAULT)

    monkeypatch.setattr(cli, "get_recorder", lambda: FakeRecorder())
    assert cli.main(["-o", str(tmp_path / "s.svg"), "--html"]) == 0
    assert ">hi</text>" in (tmp_path / "s.html").read_text(encoding="utf-8")
    assert "s.html" in capsys.readouterr().err


def test_no_html_by_default(tmp_path):
    cast = make_cast(tmp_path / "a.cast")
    assert cli.main(["render", str(cast), "-o", str(tmp_path / "a.svg")]) == 0
    assert list(tmp_path.glob("*.html")) == []


def test_html_write_failure_still_reports_the_svg(tmp_path, capsys):
    cast = make_cast(tmp_path / "a.cast")
    (tmp_path / "a.html").mkdir()  # the page cannot be written over a directory
    assert cli.main(["render", str(cast), "-o", str(tmp_path / "a.svg"), "--html"]) == 2
    err = capsys.readouterr().err
    assert (tmp_path / "a.svg").exists()
    assert f"wrote {tmp_path / 'a.svg'}" in err and "svg_recorder:" in err


def test_html_with_nameless_output_fails_cleanly(tmp_path, monkeypatch, capsys):
    cast = make_cast(tmp_path / "a.cast")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["render", str(cast), "-o", ".", "--html"]) == 2
    assert capsys.readouterr().err.startswith("svg_recorder:")


def test_cast_with_markup_in_theme_is_refused(tmp_path, capsys):
    cast = tmp_path / "evil.cast"
    theme = KITTY_DEFAULT.to_theme() | {"bg": '"/><script>alert(1)</script>'}
    import json
    cast.write_text(json.dumps({"version": 2, "width": 10, "height": 2, "theme": theme}) + "\n")
    assert cli.main(["render", str(cast), "-o", str(tmp_path / "e.svg"), "--html"]) == 2
    assert "line 1" in capsys.readouterr().err
    assert not (tmp_path / "e.svg").exists() and not (tmp_path / "e.html").exists()


def test_time_compress_option_is_parsed_for_record_and_render():
    from svg_recorder.cli import build_parsers, options_from_args
    rec, ren = build_parsers()
    assert options_from_args(rec.parse_args([])).time_compress is None
    assert options_from_args(rec.parse_args(["--time-compress", "0.2"])).time_compress == 0.2
    assert options_from_args(ren.parse_args(["x.cast", "--time-compress", "0"])).time_compress == 0.0


def test_time_compress_rejects_negative_and_non_numeric_values(capsys):
    import pytest
    from svg_recorder.cli import build_parsers
    rec, _ = build_parsers()
    for bad in ("-1", "nan", "inf", "fast"):
        with pytest.raises(SystemExit):
            rec.parse_args([f"--time-compress={bad}"])
    assert "--time-compress" in capsys.readouterr().err


def _cast(tmp_path, name="typed.cast"):
    from svg_recorder.asciicast import Header, Writer
    from svg_recorder.palette import KITTY_DEFAULT
    path = tmp_path / name
    with Writer(path, Header(20, 3, 0, KITTY_DEFAULT)) as w:
        w.write(0.0, "o", b"$ ")
        w.write(4.0, "i", b"l")
        w.write(4.01, "o", b"l")
    return path


def _loop_seconds(svg_path):
    import re
    return float(re.search(r"animation:a\d+ ([\d.]+)s", svg_path.read_text()).group(1))


def test_cast_file_as_the_command_is_rendered_with_time_compress(tmp_path, monkeypatch):
    from svg_recorder import cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "get_recorder", lambda: pytest.fail("must not record"))
    cast = _cast(tmp_path)
    assert cli.main(["--time-compress", "0.5", str(cast)]) == 0
    assert _loop_seconds(tmp_path / "typed.svg") == 2.55     # 4 s wait cut to 0.5, plus the 2 s hold
    assert cli.main([str(cast), "-o", "plain.svg"]) == 0
    assert _loop_seconds(tmp_path / "plain.svg") == 6.05
    assert cli.main(["render", str(cast), "--time-compress", "0.5", "-o", "r.svg"]) == 0
    assert (tmp_path / "r.svg").read_text() == (tmp_path / "typed.svg").read_text()
    assert cast.exists()


def test_cast_file_with_recording_only_options_is_an_error(tmp_path, monkeypatch, capsys):
    from svg_recorder import cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "get_recorder", lambda: pytest.fail("must not record"))
    cast = _cast(tmp_path)
    for extra in (["-c", "cd /"], ["-F", "pre.txt"], ["--keep-recording"]):
        assert cli.main([*extra, str(cast)]) == 2
    assert "saved recording" in capsys.readouterr().err
    assert not (tmp_path / "typed.svg").exists()


def test_a_missing_cast_name_is_still_a_command_to_record(tmp_path):
    from svg_recorder.cli import _is_cast_file
    assert not _is_cast_file(None)
    assert not _is_cast_file(str(tmp_path / "absent.cast"))
    (tmp_path / "notes.txt").write_text("x")
    assert not _is_cast_file(str(tmp_path / "notes.txt"))
    (tmp_path / "UP.CAST").write_text("x")
    assert _is_cast_file(str(tmp_path / "UP.CAST"))


def _svg_to_annotate(tmp_path, name="demo.svg", extra=()):
    cast = _cast(tmp_path)                                    # 4.01 s of events: loops every 6.05 s
    assert cli.main(["render", str(cast), "-o", str(tmp_path / name), *extra]) == 0
    return tmp_path / name


def _notes(tmp_path, text="0:01.1  Hello\n0:03.5  welcome to this recording\n"):
    path = tmp_path / "notes.txt"
    path.write_text(text)
    return path


def test_annotate_writes_a_new_svg_with_a_timed_footer(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "get_recorder", lambda: pytest.fail("must not record"))
    source = _svg_to_annotate(tmp_path)
    before = source.read_text()
    assert cli.main(["--annotate", str(_notes(tmp_path)), str(source)]) == 0
    out = (tmp_path / "demo-annotated.svg").read_text()
    assert source.read_text() == before                       # the input is left as it was
    assert 'height="51"' in before and 'height="85"' in out   # 20 columns: the second note wraps
    assert ">Hello</text>" in out and ">welcome to this</text>" in out and ">recording</text>" in out
    assert "wrote demo-annotated.svg" in capsys.readouterr().err


def test_annotate_honors_output_colors_gzip_and_html(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = _svg_to_annotate(tmp_path)
    rc = cli.main(["-a", str(_notes(tmp_path)), str(source), "-o", "out.svg", "--gzip", "--html",
                   "--footer-colors", "#123456", "#abcdef"])
    assert rc == 0
    svg = gzip.decompress((tmp_path / "out.svgz").read_bytes()).decode()
    assert "fill:#123456" in svg and "fill:#abcdef" in svg
    assert ">Hello</text>" in (tmp_path / "out.html").read_text()
    # A compressed SVG can be annotated in turn, giving it a second notes footer.
    assert cli.main(["-a", str(_notes(tmp_path, "0:02 again\n")), "out.svgz", "-o", "two.svg"]) == 0
    two = (tmp_path / "two.svg").read_text()
    assert ">Hello</text>" in two and ">again</text>" in two and 'height="102"' in two


def test_annotate_warns_about_notes_after_the_end(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    source = _svg_to_annotate(tmp_path)
    assert cli.main(["-a", str(_notes(tmp_path, "0:01 seen\n1:00 late\n")), str(source)]) == 0
    assert "left out 1 note(s)" in capsys.readouterr().err
    out = (tmp_path / "demo-annotated.svg").read_text()
    assert "seen" in out and "late" not in out


def test_annotate_input_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "get_recorder", lambda: pytest.fail("must not record"))
    source = _svg_to_annotate(tmp_path)
    notes = _notes(tmp_path)

    def fails(argv, *expect):
        assert cli.main(argv) == 2
        err = capsys.readouterr().err
        for text in expect:
            assert text in err, err

    fails(["-a", str(notes)], "needs an existing .svg file")
    fails(["-a", str(notes), "echo hi"], "needs an existing .svg file", "echo hi")
    fails(["-a", str(tmp_path / "absent.txt"), str(source)], "annotation file", "absent.txt")
    fails(["-a", str(_notes(tmp_path, "0:01 ok\nsoon: no\n")), str(source)], "line 2", "notes.txt")
    (tmp_path / "not.svg").write_text("just text")
    fails(["-a", str(_notes(tmp_path)), "not.svg"], "not.svg", "no <svg> element")
    (tmp_path / "bad.svgz").write_bytes(b"\x1f\x8bgarbage")
    fails(["-a", str(notes), "bad.svgz"], "bad.svgz")
    for flag in (["-c", "ls"], ["-F", "f"], ["--keep-recording"], ["--time-compress", "1"],
                 ["-f"], ["--cursor"], ["--no-loop"]):
        fails(["-a", str(notes), str(source), *flag], flag[0] if flag[0].startswith("--") else "cannot be used")
    assert not (tmp_path / "demo-annotated.svg").exists()


def test_the_old_annotation_switch_is_gone(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cli.main(["--annotation", "x", "true"])
    with pytest.raises(SystemExit):
        cli.main(["render", str(make_cast(tmp_path / "a.cast")), "-a", "x"])
