"""Command line entry point."""

from __future__ import annotations

import argparse
import gzip
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import __version__
from .annotations import AnnotationError, load_annotations
from .asciicast import CastError
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


def _add_render_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-t", "--time-delta", type=float, default=0.05, metavar="SECONDS",
                   help="seconds between frame captures (default 0.05)")
    p.add_argument("-f", "--footer", action="store_true", help="show the last keystrokes in a footer row")
    p.add_argument("-a", "--annotation", metavar="FILE",
                   help="with --footer, add a row describing the current keystroke")
    p.add_argument("--footer-colors", nargs=2, metavar=("BG", "FG"), default=["#303030", "#f0f0f0"],
                   help="footer background and text colors")
    p.add_argument("-o", "--output", metavar="FILE", help="SVG output file")
    p.add_argument("--cursor", action="store_true", help="render the cursor")
    p.add_argument("--no-loop", action="store_true", help="play once instead of looping")
    p.add_argument("--gzip", action="store_true", help="write gzip compressed output to a .svgz file")
    p.add_argument("--gap", type=int, default=2, help=argparse.SUPPRESS)
    p.add_argument("--full-threshold", type=float, default=0.5, help=argparse.SUPPRESS)
    p.add_argument("--no-dedup", action="store_true", help=argparse.SUPPRESS)


def build_parsers() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    rec = argparse.ArgumentParser(prog="svg_recorder",
                                  description="Record a terminal session as a small animated SVG.",
                                  epilog="Use 'svg_recorder render FILE.cast' to render a saved recording.")
    rec.add_argument("-v", "--version", action="version", version=f"svg_recorder {__version__}")
    rec.add_argument("-c", "--pre-commands", metavar="COMMANDS",
                     help="semicolon delimited shell commands to run before recording starts")
    rec.add_argument("-F", "--pre-commands-file", metavar="FILE",
                     help="file of shell commands to run before recording starts")
    rec.add_argument("--keep-recording", action="store_true",
                     help="keep the intermediate .cast file next to the SVG")
    _add_render_options(rec)
    rec.add_argument("command", nargs="?", help="command to record; omit for an interactive shell")

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
    annotations = load_annotations(args.annotation) if args.annotation else None
    return RenderOptions(
        time_delta=args.time_delta,
        gap=args.gap,
        full_threshold=args.full_threshold,
        dedup=not args.no_dedup,
        loop=not args.no_loop,
        cursor=args.cursor,
        footer=args.footer or bool(args.annotation),
        footer_colors=(args.footer_colors[0], args.footer_colors[1]),
        annotations=annotations,
    )


def _write_output(svg: str, path: Path, compress: bool) -> None:
    if compress:
        path.write_bytes(gzip.compress(svg.encode("utf-8")))
    else:
        path.write_text(svg, encoding="utf-8")


def _fail(msg: str) -> int:
    print(f"svg_recorder: {msg}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    rec_parser, ren_parser = build_parsers()

    if argv and argv[0] == "render":
        args = ren_parser.parse_args(argv[1:])
        try:
            opts = options_from_args(args)
        except (AnnotationError, OSError) as e:
            return _fail(f"annotation file: {e}")
        output = _output_path(args.output, Path(args.cast).with_suffix(".svg").name, args.gzip)
        try:
            svg = render_cast(args.cast, opts)
            _write_output(svg, output, args.gzip)
        except (CastError, OSError) as e:
            return _fail(str(e))
        print(f"wrote {output}", file=sys.stderr)
        return 0

    args = rec_parser.parse_args(argv)
    try:
        opts = options_from_args(args)
    except AnnotationError as e:
        return _fail(f"annotation file {args.annotation}: {e}")
    except OSError as e:
        return _fail(f"annotation file: {e}")
    try:
        pre_commands = read_pre_commands(args)
    except OSError as e:
        return _fail(f"pre-commands file: {e}")

    output = _output_path(args.output, default_output_name(gzip=args.gzip), args.gzip)
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
            _write_output(svg, output, args.gzip)
        except (CastError, OSError) as e:
            return _fail(str(e))
    finally:
        if tmp is not None:
            cast_path.unlink(missing_ok=True)
    print(f"wrote {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
