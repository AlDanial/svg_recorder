# svg_recorder design

Date: 2026-09-11
Status: approved in brainstorming, awaiting implementation plan

## 1. Purpose

`svg_recorder` is a command line tool for Linux and macOS, written in Python, that records
a terminal session and writes an animated SVG of it. It works like
`termtosvg` but produces much smaller files. The size win comes from emitting
only the screen cells that changed between sampled frames, as positioned
patches drawn over the previous state, instead of emitting the whole screen
for every frame.

The output must render, animated, when embedded with an `<img>` tag in a
GitHub README and on a PyPI project page. Both load the SVG through an image
proxy, so the file must be self contained: no scripts, no external fonts or
stylesheets, no references to other files, everything inline.

## 2. Command line

One console script, `svg_recorder`.

```
svg_recorder [options] [command]          # record, then render
svg_recorder render [options] recording.cast
```

With no subcommand the tool records and then renders. With no `command`
argument it starts the user's shell in a new pty; recording ends when that
shell exits. With a `command` argument the shell runs that one command and
recording ends when the command exits. The `render` subcommand reads a saved
recording and writes an SVG; this is the path for iterating on output size
without re-recording.

Options:

| Option | Meaning |
|---|---|
| `-t`, `--time-delta <seconds>` | Interval between frame samples. Default 0.05. Independent of the program's own refresh rate. |
| `-c`, `--pre-commands <string>` | Semicolon delimited shell commands run in the new shell before recording starts. |
| `-F`, `--pre-commands-file <file>` | File of shell commands, one per line, run the same way. |
| `-f`, `--footer` | Add a footer row showing the last five keystrokes. |
| `-a`, `--annotation <file>` | With `--footer`, add a second footer row with the description of the current keystroke in the current mode. |
| `--footer-colors <bg> <fg>` | Footer background and text colors, any CSS color value. Default `#303030` and `#f0f0f0`. |
| `-o`, `--output <file>` | SVG output path. Default `recording-YYYY-MM-DD-HH-MM-SS.svg`. |
| `--cursor` | Render the cursor. Off by default. |
| `--no-loop` | Play once instead of looping. |
| `--keep-recording` | Keep the intermediate `.cast` file next to the SVG. |
| `--gzip` | Write gzip compressed `.svgz`. Off by default because GitHub and PyPI do not render it. |

A missing pre-commands file or annotation file, or a malformed annotation
line, is reported and the tool exits before any pty is created.

## 3. Recording stage

Recording is the only platform-dependent stage. It sits behind a small
`Recorder` interface with one method, `record(command, pre_commands) -> path`,
so a Windows backend can be added later without touching any other module.
The first implementation is `PosixRecorder`, used on Linux and macOS. Both
provide the `pty`, `termios`, and `select` modules it relies on, and both
answer the palette queries in the terminals that support them; Terminal.app
does not, and gets the fallback palette. A future `WindowsRecorder` would
wrap ConPTY through pywinpty, use threads instead of `select`, enable virtual
terminal input so keys arrive as the same escape sequences, and use a
shell-specific sentinel command; key decoding and everything after the
intermediate file are unchanged.

The recorder opens a pty sized to the current terminal, spawns the user's
shell in it, puts the real terminal in raw mode, and shuttles bytes both ways
with `select`. Bytes from the child are timestamped and appended to the
recording as output events. Bytes from the user are forwarded to the child
and appended as input events.

Pre-commands run before recording begins. The recorder writes them to the
shell, followed by a command that prints a random sentinel string, and
discards all output until the sentinel appears. It then clears the screen,
resets the clock, and starts capturing. Because the pre-commands ran in the
same shell process, any `cd`, `export`, or alias they set is in effect for
the recorded command, but their output is not in the recording.

Before spawning, the recorder sends OSC 10, 11, and 4 queries to the real
terminal and reads the replies with a short timeout, so the recording carries
the foreground, background, and 16-color palette the user actually saw. If
nothing answers, the kitty default palette is used.

If the child dies unexpectedly, whatever was captured is still rendered.

### Intermediate format

The recording is an asciicast v2 file, asciinema's format: a JSON header
line followed by one JSON event per line, each `[time, "o"|"i", data]`.
Two extra keys are added to the header: `palette`, the captured colors, and
`cell`, the pixel width and height used for layout. Files produced by
asciinema itself render too; they just fall back to the default palette.

## 4. Rendering stage

### 4.1 Sampling

Rendering replays the recording through a pyte screen. A clock advances in
steps of the time delta. At each tick, every output event up to that time is
fed to pyte and the screen is sampled. Input events never touch the screen;
they only drive the footer.

### 4.2 Patch detection

Each sample is compared cell by cell with the last emitted frame, not the
previous sample. A cell is the tuple (character, foreground, background,
bold, italic, underline, reverse). If no cell differs, nothing is emitted for
the tick, so idle time costs zero bytes. Only rows pyte marks dirty are
compared.

Changed cells become patches in two passes:

1. Row runs. Within a row, changed cells that are adjacent or separated by at
   most two unchanged cells merge into one run. The gap tolerance is a tuning
   knob measured by the size harness.
2. Rectangle merging. Runs on consecutive rows with the same column extent
   stack into one rectangular patch.

A patch is (column, row, width, list of row contents). A single changed
character is a 1 by 1 patch; no separate mechanism is needed for the
"few consecutive characters" case, and the SVG encoding drops attributes
that are redundant for one-row patches.

If more than half the screen changed, the whole screen is emitted as one
patch. The threshold is a tuning knob.

When `--cursor` is on, the cursor position counts as a cell change and flows
through the same path.

### 4.3 SVG structure

The document has a `<style>` block, a `<defs>` block for shared patch bodies,
and the patches in time order. Coordinates are pixels with integer cell width
and height. Every text element carries `textLength` so glyphs are fitted to
the cell grid whatever font the viewer substitutes. The root carries
`xml:space="preserve"`.

A patch is one group:

```
<g class="t12"><rect x="64" y="34" width="120" height="51" class="B"/>
<text x="64" y="47" textLength="120" class="a"><tspan>hello wor</tspan><tspan x="64" dy="17">ld again</tspan></text></g>
```

The rect erases what was under the patch. One text element holds all rows as
tspans. A one-row patch drops the rect when its background is the default
and drops the tspan wrapper. Runs with different styles inside a row become
extra tspans with a class; differing backgrounds become extra rects. Colors,
bold, italic, and underline are CSS classes with one or two letter names
defined once in the style block.

Font: `DejaVu Sans Mono, Menlo, Consolas, monospace` at 14px. Wide
characters occupy two cells, using wcwidth. 256-color and truecolor
attributes are supported as pyte parses them.

### 4.4 Timing

Timing uses CSS so it works inside an image tag on GitHub and PyPI. Each
distinct frame time gets a class.

- Looping (default): the class points to a `@keyframes` rule that holds the
  group hidden until its percentage of the total duration and visible after,
  with `steps(1,end)` timing. On restart everything hides again, which
  resets the accumulated patches. Total duration is the recording length
  plus a two second hold on the final frame.
- `--no-loop`: all groups share one keyframes rule and the class sets only an
  animation delay, with `fill-mode: forwards`.

Document order gives painter's order, so a later patch covers an earlier one
at the same place.

### 4.5 Deduplication and byte discipline

Any patch body seen more than once moves into `<defs>` and later occurrences
become a `<use>` carrying only position and time class. Output has no
indentation or newlines, short ids, three digit hex colors when reducible,
and no attribute equal to its SVG default.

## 5. Footer and annotations

With `--footer`, the virtual screen gains one extra row below the terminal
rows, or two with `--annotation`, drawn in the footer colors. Footer text is
written into those rows like program output and the same diff and patch
machinery emits the changes.

### 5.1 Key names

Input bytes decode to names: bytes 1 to 26 become `<Ctrl>-x` with the
lowercase letter (Ctrl-x and Ctrl-X are not distinguished, and Ctrl-I, Ctrl-M,
Ctrl-[ show as Tab, Enter, Esc); escape followed by a character within 50 ms
becomes `<Alt>-x`; escape followed by a byte 1 to 26 becomes `<Ctrl>-<Alt>-x`; a bare escape
after 50 ms is `<Esc>`. CSI and SS3 sequences map to `<UpArrow>`,
`<DownArrow>`, `<LeftArrow>`, `<RightArrow>`, `<PgUp>`, `<PgDn>`, `<Home>`,
`<End>`, `<Insert>`, `<Delete>`, `<F1>`..`<F12>`. Printable characters show
as themselves, space as `<Space>`, backspace as `<Backspace>`. Anything
unrecognized shows as its hex bytes.

### 5.2 Footer row

Shows the last five keys, oldest left, newest in bold. Bold reverts to
normal two seconds after the last key, implemented by scheduling a footer
change at that time so it flows through the normal ticks.

### 5.3 Annotation file

Two kinds of lines. A mode line is `mode <name> <regex>`. A keystroke line is
`<name> <key> <description>`; everything after the key is the description.
Blank lines and lines starting with `#` are ignored. Example:

```
mode code-view-debug ^.*\[DEBUG\].*$
mode code-view-navigate ^.*\[NAV\].*$
code-view-debug <Ctrl>-b switch to breakpoint view
code-view-navigate / open search textbox
code-view-debug c continue execution
```

At each tick, modes are tested in file order against every screen row; the
first match is the current mode. The second footer row shows the description
for the most recent key in that mode, or is blank when there is no entry. It
updates on every keystroke and whenever the mode changes. A malformed line is
reported with its line number and the file is rejected before recording.

## 6. Testing

Unit tests run without a terminal or display:

- Key decoding: bytes in, names out, including the escape timeout.
- Patch detection: two synthetic screens in, patches out. Single character,
  row run with a gap, stacked rectangle, whole-screen repaint, no change.
- SVG writer: patches in, string out. Structure, dedup yielding a `<use>`,
  and a scan proving there are no external references.
- Annotation parsing: grammar, and rejection of a bad line with its number.
- Recording round trip: a fake child writing known bytes at known times
  through a real pty, checked against the asciicast written.

Visual checks done by hand, once early with a tiny hand-written recording:
render, load in a browser as an image tag, confirm alignment and animation.

### Size harness

`tools/sizes.py` takes one or more recordings, renders each under named
strategy variants (gap tolerance, whole-screen threshold, dedup on or off,
loop versus single play), and prints a table of bytes per variant. The
recording of the tdb test case is checked in as a fixed benchmark. A
termtosvg render of the same recording, produced in an isolated tool
environment, is the baseline to beat.

Producing the benchmark recording, in a kitty window:

```
svg_recorder --keep-recording -o benchmark.svg
```

This opens a shell in a new pty and starts recording. In that shell, enter:

```
cd git/tests
tdb --replay-quiet --replay-interval 0.5 --replay-tui session.txt
exit
```

The replay ends with a quit action, so tdb returns to the shell on its own,
and `exit` ends the recording. The `.cast` file kept alongside the SVG is
what the harness and the termtosvg baseline consume.

## 7. Repository layout and packaging

```
git/
  pyproject.toml
  src/svg_recorder/
    cli.py          argument parsing, record-then-render flow, render subcommand
    recorder.py     Recorder interface and backend selection by platform
    recorder_posix.py  pty spawn, byte shuttling, pre-command sentinel, palette query
    asciicast.py    read and write the intermediate format
    keys.py         input bytes to key names
    annotations.py  annotation file parsing and mode matching
    screen.py       pyte replay, sampling clock, footer rows
    patches.py      cell diff, row runs, rectangle merging
    svgwriter.py    patches to SVG text, dedup, style block
    palette.py      kitty default colors and the OSC reply parser
  tests/            one test file per module, plus the tdb fixtures
  tools/sizes.py    the size harness
  docs/superpowers/specs/
```

Dependencies: pyte and wcwidth. Python 3.11 or later. Supported platforms are
Linux and macOS; Windows is a planned follow-on behind the Recorder interface. setuptools backend,
version as a plain string in the package, console script `svg_recorder`,
dev extras pytest and pytest-cov. MIT licence. tdb is not a dependency.

## 8. Decisions recorded from brainstorming

- Mode detection is by regex on screen content, declared in the annotation file.
- Ctrl letter case is not distinguished.
- Interface follows termtosvg: a new pty with a shell, optional single command.
- Pre-commands run in the new shell before recording begins and are not recorded.
- No special per-terminal support; the palette query is the only terminal interaction.
- Cursor rendering is a flag, off by default.
- Idle gap compression is not implemented; idle time is free in the patch model.
- Linux and macOS are supported in the first implementation. Windows is a
  later sub-project; the recorder interface exists so it stays contained.
