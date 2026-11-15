# svg_recorder

Record a terminal session as a small animated SVG.

    svg_recorder            # opens a shell; exit the shell to stop recording
    svg_recorder "cmd"      # records one command and stops when it exits
    svg_recorder render recording.cast -o out.svg
    svg_recorder render recording.cast -o out.svg --html   # also writes out.html

Pre-commands run in a non-interactive shell, so put aliases in your shell rc file rather than in pre-commands.

The SVG animates inside an `<img>` tag on GitHub and PyPI. On PyPI the README
must reference the absolute raw GitHub URL of the SVG, since PyPI cannot
resolve relative paths.

## Options

```
positional arguments:
  command               command to record; omit for an interactive shell

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -c, --pre-commands COMMANDS
                        semicolon delimited shell commands to run before recording starts
  -F, --pre-commands-file FILE
                        file of shell commands to run before recording starts
  --keep-recording      keep the intermediate .cast file next to the SVG
  -t, --time-delta SECONDS
                        seconds between frame captures (default 0.05)
  -f, --footer          show the last keystrokes in a footer row
  -a, --annotation FILE
                        with --footer, add a row describing the current keystroke
  --footer-colors BG FG
                        footer background and text colors
  -o, --output FILE     SVG output file
  --cursor              render the cursor
  --no-loop             play once instead of looping
  --gzip                write gzip compressed output to a .svgz file
  --html                also write an .html page that plays the SVG with
                        playback controls
```

Use 'svg_recorder render FILE.cast' to render a saved recording.

## HTML player

`--html` writes a page next to the SVG (`out.svg` gives `out.html`) that
embeds the recording and adds play/pause, restart, a scrubber and a speed
control.  Keys: space plays or pauses, the left and right arrows seek one
second, `,` and `.` step 50 ms, `r` restarts.

The page is a single self-contained file with no external scripts, styles or
fonts, so it can be opened straight from disk or published as is, for example
on GitHub Pages: commit `out.html` to the Pages branch and open
`https://USER.github.io/REPO/out.html`.  It needs no Jekyll configuration and
can be embedded in another page with an `<iframe>`.  The page carries its own
copy of the recording, so the `.svg` file does not have to be published with it.
Two things to watch: `--html` replaces any existing `.html` file of the same
name (so `-o index.svg --html` overwrites `index.html`), and GitHub Pages does
not publish files whose names start with `_` or `.`.

## Benchmarks

For the tdb TUI session in `tests/benchmark.cast`: default renders at 175,932 bytes (15,816 bytes gzipped), versus termtosvg's 2,022,472 bytes (138,572 bytes gzipped). The default is **11.5×** smaller raw and **8.8×** smaller gzipped.

Reproduce with: `uv run python tools/sizes.py tests/benchmark.cast`
