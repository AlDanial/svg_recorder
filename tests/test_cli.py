import gzip
import tempfile
from datetime import datetime

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


def test_render_footer_and_annotation_options(tmp_path):
    # Footer text is truncated to the terminal width (screen.py Footer._line,
    # by design -- see test_footer_truncates_to_width in test_screen.py), so
    # this cast needs a wider terminal than the 10-column default to fit the
    # full "key k does things" annotation description.
    cast = make_cast(tmp_path / "a.cast", width=20)
    ann = tmp_path / "ann.txt"
    ann.write_text("mode m hi\nm k key k does things\n")
    out = tmp_path / "a.svg"
    rc = cli.main(["render", str(cast), "-o", str(out), "-f", "-a", str(ann),
                   "--footer-colors", "#111111", "#eeeeee"])
    assert rc == 0
    svg = out.read_text()
    assert "key k does things" in svg and "#111111" in svg


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


def test_bad_annotation_file_fails_before_recording(tmp_path, capsys):
    ann = tmp_path / "ann.txt"
    ann.write_text("mode\n")
    rc = cli.main(["-f", "-a", str(ann), "true"])
    assert rc == 2
    assert "line 1" in capsys.readouterr().err


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
