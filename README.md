# svg_recorder

Record a terminal session as a small animated SVG.

    svg_recorder            # opens a shell; exit the shell to stop recording
    svg_recorder "cmd"      # records one command and stops when it exits
    svg_recorder render recording.cast -o out.svg

Pre-commands run in a non-interactive shell, so put aliases in your shell rc file rather than in pre-commands.

The SVG animates inside an `<img>` tag on GitHub and PyPI. On PyPI the README
must reference the absolute raw GitHub URL of the SVG, since PyPI cannot
resolve relative paths.

## Benchmarks

For the tdb TUI session in `tests/benchmark.cast`: default renders at 175,932 bytes (15,816 bytes gzipped), versus termtosvg's 2,022,472 bytes (138,572 bytes gzipped). The default is **11.5×** smaller raw and **8.8×** smaller gzipped.

Reproduce with: `uv run python tools/sizes.py tests/benchmark.cast`
