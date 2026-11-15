# HTML Player Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `--html` writes `foo.html` next to `foo.svg`: a self-contained player page that inlines the SVG and adds playback controls, and displays correctly on GitHub Pages.

**Architecture:** A real HTML template ships as package data (`player.html`). `html.py` substitutes the SVG and a title into it. `cli.py` calls it after writing the SVG on both the record and render paths.

**Tech Stack:** Python 3.11+, `importlib.resources`, setuptools package-data, plain HTML/CSS/JS (Web Animations API), pytest.

**Spec:** `docs/superpowers/specs/2026-11-14-html-player-design.md`

## Global Constraints

- Player markup uses ids and id-scoped element selectors only: no `class=` attributes and no `<text>` elements in the template (the inlined SVG's stylesheet is document-wide).
- One self-contained file: no `src=`, `href=` (other than `#fragment`), `url(`, `@import` or `@font-face` in the template.
- The page starts with `<!DOCTYPE html>` (no YAML front matter), declares `<meta charset="utf-8">`, and is written with `encoding="utf-8"`.
- No absolute or root-relative URLs.
- Template read with `importlib.resources.files("svg_recorder")`; no `__file__` path arithmetic.
- Finish with `uv run pytest` green.

## Review Focus

- `-o page.html --html`: the page would overwrite the SVG; expect exit 2 and a clear message, nothing written. (Task 2)
- `-o out` (no suffix) or `-o a.b.svg`: page goes to `out.html` / `a.b.html`. (Task 2)
- Recorded text containing `{{ x }}`, `{% y %}`, `\1`, `$&` or the marker comment itself survives verbatim and is substituted exactly once. (Task 1)
- File stem with `<`, `&` or `"` is escaped in `<title>` and the title bar. (Task 1)
- A recording with no animated frames (a single static frame): controls are disabled, no division by zero, no script error. (Task 3, browser check)

---

### Task 1: Template and `wrap_svg`

**Files:**
- Create: `src/svg_recorder/player.html` (moved from `shell.html`, restyled; `git rm`-equivalent: delete the untracked `shell.html`)
- Create: `src/svg_recorder/html.py`
- Modify: `pyproject.toml` (add `[tool.setuptools.package-data]` with `svg_recorder = ["*.html"]`)
- Test: `tests/test_html.py`

**Interfaces:**
- Produces: `svg_recorder.html.wrap_svg(svg: str, title: str) -> str`; `svg_recorder.html.SVG_MARKER = "<!-- The SVG content goes here -->"`; `svg_recorder.html.TITLE_MARKER = "%TITLE%"`, which appears in the template's `<title>` and in the title bar.

- [ ] **Step 1: Write failing tests** in `tests/test_html.py`:
  - `test_wrap_inserts_svg_once`: `wrap_svg("<svg>X</svg>", "a")` contains `<svg>X</svg>` exactly once and no `SVG_MARKER`, no `%TITLE%`.
  - `test_wrap_starts_with_doctype`: result starts with `<!DOCTYPE html>` and contains `<meta charset="utf-8">`.
  - `test_wrap_preserves_special_text`: an svg containing `{{ x }} {% y %} \1 $& %TITLE% <!-- The SVG content goes here -->` appears verbatim, exactly once.
  - `test_wrap_escapes_title`: title `a<b>&"c` appears as `a&lt;b&gt;&amp;&quot;c`, never raw.
  - `test_template_is_self_contained_and_classless`: the template text has no `class=`, `<text`, `src=`, `url(`, `@import`, `@font-face`, and no `href=` except `href="#`.
- [ ] **Step 2:** `uv run pytest tests/test_html.py` fails on import.
- [ ] **Step 3: Implement `html.py`.** Split the template on the markers rather than chaining `str.replace`, so substituted content is never rescanned: title first on the template halves, SVG joined in last. Escape with `html.escape(title, quote=True)`.
- [ ] **Step 4: Write `player.html`** per the spec's Design section: window card (title bar with three dots drawn as CSS circles and the title), fluid SVG, control bar (play/pause toggle, restart, scrubber with filled progress, time readout, speed select), keyboard (space, left/right = 1 s, `r`), `prefers-reduced-motion` starts paused. Script behaviour:
  - span = max over animations of `delay + duration * (iterations === Infinity ? 1 : iterations)`; looping = any animation with infinite iterations.
  - displayed time = `currentTime % span` when looping, `min(currentTime, span)` otherwise; play-once reaching the end flips the toggle back to "play", and pressing play at the end restarts.
  - span 0: disable all controls.
  - page background and card colour derived from the SVG's first `<rect>` fill.
- [ ] **Step 5:** `uv run pytest tests/test_html.py` passes.

### Task 2: `--html` switch

**Files:**
- Modify: `src/svg_recorder/cli.py`
- Modify: `README.md` (options block, one usage line, short GitHub Pages note)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `wrap_svg(svg, title)`.
- Produces: `--html` flag on both parsers; `cli._write_html(svg: str, output: Path) -> Path` writing `output.with_suffix(".html")` with title `output.stem`.

- [ ] **Step 1: Write failing tests** in `tests/test_cli.py`:
  - `test_html_render_writes_page_next_to_svg`: `render a.cast -o a.svg --html` returns 0; `a.svg` and `a.html` exist; page contains the SVG text and `>hi</text>`; stderr names both files.
  - `test_html_with_gzip`: `--gzip --html` gives `a.svgz` and a plain-text `a.html` containing `<svg`.
  - `test_html_suffix_handling`: `-o out` gives `out.html`; `-o a.b.svg` gives `a.b.html`.
  - `test_html_refuses_html_output_name`: `-o a.html --html` returns 2, stderr mentions `--html`, neither file is written.
  - `test_html_record_path`: with `get_recorder` monkeypatched as the existing record-path tests do, `--html` writes the page.
  - `test_no_html_by_default`: without the flag no `.html` appears.
- [ ] **Step 2:** tests fail with "unrecognized arguments: --html".
- [ ] **Step 3: Implement.** Add the flag in `_add_render_options`. Fold "write SVG, optionally write page, print wrote line" into one helper used by both paths so they cannot diverge; check the `.html` collision before recording starts (record path) and before rendering (render path).
- [ ] **Step 4:** `uv run pytest` passes in full.
- [ ] **Step 5:** Update README.

### Task 3: Browser and GitHub Pages check

- [ ] **Step 1:** Render `tests/benchmark.cast` with `--html` (looping, `--no-loop`, and a one-frame cast) into the scratchpad.
- [ ] **Step 2:** Serve the directory over HTTP under a sub-path, load each page in a headless browser, and confirm: no console errors, animations found, scrub changes the visible frame, the time readout advances, layout holds at 360 px and 1400 px widths, and inside an `<iframe>`.
- [ ] **Step 3:** Build the wheel (`uv build`) and confirm `player.html` is inside it.
