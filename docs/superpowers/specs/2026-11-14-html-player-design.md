# `--html` player page: design

## Intent

`--html` writes a standalone HTML page next to the SVG.  The page inlines the
SVG and adds playback controls (play/pause, restart, scrub, speed), so a
recording can be reviewed frame by frame and published as a web page,
in particular on GitHub Pages.

## Goals

- `foo.svg` gets a sibling `foo.html`; the SVG is still written as before.
- Works for both the record path and `svg_recorder render`.
- With `--gzip`: `foo.svgz` plus an uncompressed `foo.html`.
- One self-contained file: no external scripts, styles, fonts or images.
- Displays correctly when served by GitHub Pages (see Constraints).
- An elegant, restrained look: the recording in a terminal-window card, a slim
  control bar underneath.

## Non-goals

- No change to the looping SVG output.  (The play-once output changed by one
  keyword during the work: its 1 ms reveal uses `steps(1,start)` instead of
  `steps(1,end)`, because Chrome left frames hidden once they had finished.)
- No HTML-only mode (the SVG is always written).
- No theming options on the command line.

## Constraints

- **Stylesheet leak.** Inlined in HTML, the SVG's `<style>` is document-wide:
  `text`, `.b`, `.i`, `.u`, `.e`, `.fN`, `.gN`, `.tN` and `[class^=t]`.  The
  player markup therefore uses ids and element selectors scoped under ids,
  never classes, and its own icons contain no `<text>`.
- **GitHub Pages.**
  - Pages runs Jekyll, which only processes files that start with YAML front
    matter.  The page starts with `<!DOCTYPE html>`, so recorded text such as
    `{{ x }}` or `{% y %}` is served verbatim.
  - The file is UTF-8 with `<meta charset="utf-8">` (Pages also sends
    `charset=utf-8`).
  - No absolute or root-relative URLs, so it works under a project path
    (`user.github.io/repo/`) and from `file://`.
  - Inline `<script>` and `<style>` only; Pages sends no CSP that blocks them.
  - Must behave inside an `<iframe>` on another page: fluid width, no
    fixed heights, no reliance on focus.
- Cross-platform: the template is read with `importlib.resources`, written
  with `encoding="utf-8"`.

## Approaches

1. **Template file shipped as package data** (chosen).  `shell.html` becomes
   `src/svg_recorder/player.html`; the SVG replaces the marker comment.  The
   template stays a real HTML file that can be opened and edited on its own.
2. Template as a Python string constant.  No packaging change, but the HTML,
   CSS and JS lose editor support and the sample file stops being the source.
3. A page that references the `.svg` with `<img>`/`<object>`.  Rejected:
   animations inside `<img>` cannot be scripted, and `<object>` needs two files
   and breaks from `file://` in some browsers.

## Design

- `cli.py`: `--html` in `_add_render_options`; after the SVG is written, both
  paths call one helper that writes `output.with_suffix(".html")`.  The
  "wrote ..." message lists the HTML file too.  `OSError` is reported like
  other output failures.
- `html.py`: `wrap_svg(svg, title) -> str` loads the template and substitutes
  the SVG and the title (escaped file stem).  The page script reads the
  recording's background colour and whether it loops from the SVG itself, so
  Python passes nothing else.
- `--html` with an output name that already ends in `.html` is an error, since
  the page would overwrite the SVG.
- `player.html`:
  - window card: rounded corners, soft shadow, title bar with the file name;
    the SVG scales to the available width.
  - controls: play/pause toggle, restart, scrubber with filled progress, time
    readout, speed select.  Inline SVG icons built from paths.
  - keyboard: space toggles, left/right step, `r` restarts.
  - time: wraps at the loop length when looping, clamps at the end otherwise;
    a finished play-once recording shows the play icon again.
  - honours `prefers-reduced-motion` by starting paused.
- `pyproject.toml`: `[tool.setuptools.package-data] svg_recorder = ["*.html"]`.
- Tests: switch on both paths, naming, `--gzip` combination, marker replaced,
  no class attributes or external references in the template, recorded
  `{{ }}` text preserved, title escaped.
- README: option list and a short GitHub Pages note.
