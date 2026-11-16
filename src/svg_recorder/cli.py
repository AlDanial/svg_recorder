"""Command line entry point."""

from __future__ import annotations

import argparse
import gzip
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import __version__
from .annotations import AnnotationError, SvgError, annotate_svg, load_annotations, loop_duration
from .asciicast import CastError
from .html import wrap_svg
from .recorder import RecordError, get_recorder
from .render import RenderOptions, render_cast


def default_output_name(now: datetime | None = None, gzip: bool = False) -> str:
    now = now or datetime.now()
    suffix = ".svgz" if gzip else ".svg"
    return now.strftime("recording-%Y-%m-%d-%H-%M-%S") + suffix


def _output_path(name: str | None, default: str, compress: bool) -> Path:
    """The output path, with a '.svg' suffix turned into '.svgz' under --gzip."""
    path = Path(name or default)
    if compress and path.suffix == ".svg":
        path = path.with_suffix(".svgz")
    return path


def _seconds(text: str) -> float:
    """An argparse type for a duration: a finite number that is not negative."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number of seconds: {text!r}") from None
    if not (0 <= value < float("inf")):
        raise argparse.ArgumentTypeError(f"seconds must be 0 or more: {text!r}")
    return value


def _add_render_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-t", "--time-delta", type=float, default=0.05, metavar="SECONDS",
                   help="seconds between frame captures (default 0.05)")
    p.add_argument("--time-compress", type=_seconds, metavar="X",
                   help="shorten pauses spent waiting for a keystroke to at most X seconds; "
                        "works with a command to record or an existing .cast file")
    p.add_argument("-f", "--footer", action="store_true", help="show the last keystrokes in a footer row")
    p.add_argument("--footer-colors", nargs=2, metavar=("BG", "FG"), default=["#303030", "#f0f0f0"],
                   help="footer background and text colors, also used by --annotate")
    p.add_argument("-o", "--output", metavar="FILE", help="SVG output file")
    p.add_argument("--cursor", action="store_true", help="render the cursor")
    p.add_argument("--no-loop", action="store_true", help="play once instead of looping")
    p.add_argument("--gzip", action="store_true", help="write gzip compressed output to a .svgz file")
    p.add_argument("--html", action="store_true",
                   help="also write an .html page that plays the SVG with playback controls")
    p.add_argument("--gap", type=int, default=2, help=argparse.SUPPRESS)
    p.add_argument("--full-threshold", type=float, default=0.5, help=argparse.SUPPRESS)
    p.add_argument("--no-dedup", action="store_true", help=argparse.SUPPRESS)


def build_parsers() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    rec = argparse.ArgumentParser(prog="svg_recorder",
                                  description="Record a terminal session as a small animated SVG.",
                                  epilog="Use 'svg_recorder FILE.cast' or 'svg_recorder render FILE.cast' "
                                         "to render a saved recording, and "
                                         "'svg_recorder --annotate NOTES FILE.svg' to add timed notes to an SVG.")
    rec.add_argument("-v", "--version", action="version", version=f"svg_recorder {__version__}")
    rec.add_argument("-c", "--pre-commands", metavar="COMMANDS",
                     help="semicolon delimited shell commands to run before recording starts")
    rec.add_argument("-F", "--pre-commands-file", metavar="FILE",
                     help="file of shell commands to run before recording starts")
    rec.add_argument("--keep-recording", action="store_true",
                     help="keep the intermediate .cast file next to the SVG")
    rec.add_argument("-a", "--annotate", metavar="FILE",
                     help="add a footer of timed notes to an existing SVG, given in place of the command; "
                          "each line of FILE is a time (M:S or M:S.F) followed by the text to show from then on")
    _add_render_options(rec)
    rec.add_argument("command", nargs="?",
                     help="command to record; omit for an interactive shell. "
                          "An existing .cast file is rendered instead of recorded. "
                          "With --annotate, the existing .svg file to add notes to")

    ren = argparse.ArgumentParser(prog="svg_recorder render",
                                  description="Render a saved recording to SVG.")
    ren.add_argument("cast", help="asciicast v2 file")
    _add_render_options(ren)
    return rec, ren


def read_pre_commands(args: argparse.Namespace) -> list[str]:
    commands: list[str] = []
    if args.pre_commands_file:
        text = Path(args.pre_commands_file).read_text(encoding="utf-8")
        commands += [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    if args.pre_commands:
        commands += [c.strip() for c in args.pre_commands.split(";") if c.strip()]
    return commands


def options_from_args(args: argparse.Namespace) -> RenderOptions:
    return RenderOptions(
        time_delta=args.time_delta,
        gap=args.gap,
        full_threshold=args.full_threshold,
        dedup=not args.no_dedup,
        loop=not args.no_loop,
        cursor=args.cursor,
        footer=args.footer,
        footer_colors=(args.footer_colors[0], args.footer_colors[1]),
        time_compress=args.time_compress,
    )


def _html_path(output: Path) -> Path:
    """The player page that --html writes next to the SVG."""
    return output.with_suffix(".html")


def _html_clash(output: Path, html: bool) -> str | None:
    """An error message if the --html page would overwrite the SVG itself."""
    # Compared without case: Windows and macOS file names are case-insensitive.
    if not html:
        return None
    try:
        page = _html_path(output)
    except ValueError:  # no file name to hang .html on, as in "-o ."
        return f"--html cannot name a page for the output {output}"
    if output.name.lower() == page.name.lower():
        return (f"--html would write its page over the SVG output {output}; "
                "give the SVG a different name, such as one ending in .svg")
    return None


def _write_outputs(svg: str, path: Path, compress: bool, html: bool) -> None:
    """Write the SVG, and with --html its player page, reporting each one."""
    if compress:
        path.write_bytes(gzip.compress(svg.encode("utf-8")))
    else:
        path.write_text(svg, encoding="utf-8")
    # Reported before the page is attempted: if that fails, the SVG still exists.
    print(f"wrote {path}", file=sys.stderr)
    if html:
        # The page always embeds the plain SVG, even next to a .svgz.
        page = _html_path(path)
        page.write_text(wrap_svg(svg, path.stem), encoding="utf-8")
        print(f"wrote {page}", file=sys.stderr)


def _fail(msg: str) -> int:
    print(f"svg_recorder: {msg}", file=sys.stderr)
    return 2


def _is_cast_file(command: str | None) -> bool:
    """True when the 'command' to record is really a saved recording to render."""
    return bool(command) and command.lower().endswith(".cast") and Path(command).is_file()


def _render(args: argparse.Namespace) -> int:
    """Render the saved recording args.cast to SVG."""
    opts = options_from_args(args)
    output = _output_path(args.output, Path(args.cast).with_suffix(".svg").name, args.gzip)
    if clash := _html_clash(output, args.html):
        return _fail(clash)
    try:
        svg = render_cast(args.cast, opts)
        _write_outputs(svg, output, args.gzip, args.html)
    except (CastError, OSError) as e:
        return _fail(str(e))
    return 0


# Options that shape a recording or its rendering and so mean nothing to --annotate.
_NOT_WITH_ANNOTATE = {
    "pre_commands": "--pre-commands", "pre_commands_file": "--pre-commands-file",
    "keep_recording": "--keep-recording", "time_compress": "--time-compress",
    "footer": "--footer", "cursor": "--cursor", "no_loop": "--no-loop",
}


def _read_svg(path: Path) -> str:
    """The text of an .svg file, or of a gzip compressed .svgz one."""
    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8")


def _annotate(args: argparse.Namespace) -> int:
    """Add the notes in args.annotate as a footer to the SVG named as the command."""
    if not args.command:
        return _fail("--annotate needs an existing .svg file to add the notes to")
    source = Path(args.command)
    if not source.is_file():
        return _fail(f"--annotate needs an existing .svg file, and {source} is not one")
    unused = [flag for dest, flag in _NOT_WITH_ANNOTATE.items()
              if getattr(args, dest) not in (None, False)]
    if unused:
        return _fail(f"{', '.join(unused)} cannot be used with --annotate, which only adds notes to an SVG")
    try:
        notes = load_annotations(args.annotate)
    except AnnotationError as e:
        return _fail(f"annotation file {args.annotate}: {e}")
    except (OSError, UnicodeDecodeError) as e:
        return _fail(f"annotation file: {e}")
    output = _output_path(args.output, source.stem + "-annotated.svg", args.gzip)
    if clash := _html_clash(output, args.html):
        return _fail(clash)
    try:
        svg = _read_svg(source)
        duration = loop_duration(svg)
        annotated = annotate_svg(svg, notes, (args.footer_colors[0], args.footer_colors[1]))
    except (OSError, EOFError, UnicodeDecodeError) as e:  # EOFError: a truncated .svgz
        return _fail(f"{source}: {e}")
    except SvgError as e:
        return _fail(f"{source}: {e}")
    late = [t for t, _ in notes if duration is not None and t >= duration]
    if late:
        print(f"svg_recorder: left out {len(late)} note(s) timed at or after the end of the "
              f"{duration:g} second animation", file=sys.stderr)
    try:
        _write_outputs(annotated, output, args.gzip, args.html)
    except OSError as e:
        return _fail(str(e))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    rec_parser, ren_parser = build_parsers()

    if argv and argv[0] == "render":
        return _render(ren_parser.parse_args(argv[1:]))

    args = rec_parser.parse_args(argv)
    if args.annotate:
        return _annotate(args)
    if _is_cast_file(args.command):
        # 'svg_recorder FILE.cast' is shorthand for 'svg_recorder render FILE.cast'.
        if args.pre_commands or args.pre_commands_file or args.keep_recording:
            return _fail(f"{args.command} is a saved recording, which is rendered, not recorded; "
                         "--pre-commands, --pre-commands-file and --keep-recording do not apply")
        args.cast = args.command
        return _render(args)
    opts = options_from_args(args)
    try:
        pre_commands = read_pre_commands(args)
    except OSError as e:
        return _fail(f"pre-commands file: {e}")

    output = _output_path(args.output, default_output_name(gzip=args.gzip), args.gzip)
    if clash := _html_clash(output, args.html):
        return _fail(clash)
    if args.keep_recording:
        cast_path = output.with_suffix(".cast")
        tmp = None
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".cast", delete=False)
        tmp.close()
        cast_path = Path(tmp.name)
    try:
        try:
            get_recorder().record(args.command, pre_commands, cast_path)
        except RecordError as e:
            return _fail(str(e))
        try:
            svg = render_cast(cast_path, opts)
            _write_outputs(svg, output, args.gzip, args.html)
        except (CastError, OSError) as e:
            return _fail(str(e))
    finally:
        if tmp is not None:
            cast_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
