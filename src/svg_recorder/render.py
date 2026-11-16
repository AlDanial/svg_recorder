"""Recording to SVG: sample, diff, write."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .annotations import Annotations
from .asciicast import Event, Header, read
from .keys import ESC_TIMEOUT
from .patches import blank_frame, diff_frames
from .screen import Footer, Sampler
from .svgwriter import SvgWriter


@dataclass
class RenderOptions:
    time_delta: float = 0.05
    gap: int = 2
    full_threshold: float = 0.5
    dedup: bool = True
    loop: bool = True
    hold: float = 2.0
    cursor: bool = False
    footer: bool = False
    footer_colors: tuple[str, str] = ("#303030", "#f0f0f0")
    annotations: Annotations | None = None
    time_compress: float | None = None


def compress_time(events: list[Event], limit: float) -> list[Event]:
    """Shorten the waits that slow typing leaves in a recording.

    A pause that ends with input -- the recorder waiting for the next key --
    is cut down to `limit` seconds, as is the pause after the first output,
    which is the wait between the first two frames.  Later events move earlier
    by the time removed; pauses already shorter than `limit` and pauses that
    end with output (a program working) are left alone.
    """
    out: list[Event] = []
    removed = 0.0
    prev_t: float | None = None
    seen_output = after_first_output = False
    esc_t: float | None = None  # original time of a bare Esc key still awaiting its timeout
    for t, kind, data in events:
        if prev_t is not None:
            gap = t - prev_t
            if gap > limit and (kind == "i" or after_first_output):
                removed += gap - limit
        if kind == "i":
            # A lone Esc is told apart from the start of an escape sequence by
            # the pause after it; keep enough of that pause for it to stay one.
            if esc_t is not None and t - esc_t > ESC_TIMEOUT:
                squeezed = (t - removed) - out_esc_t
                if squeezed <= ESC_TIMEOUT:
                    removed -= min(t - esc_t, 2 * ESC_TIMEOUT) - squeezed
            esc_t = t if data == b"\x1b" else None
            out_esc_t = t - removed
        out.append((round(t - removed, 6), kind, data))
        after_first_output = kind == "o" and bool(data) and not seen_output
        seen_output = seen_output or after_first_output
        prev_t = t
    return out


def render_events(header: Header, events: list[Event], opts: RenderOptions) -> str:
    if opts.time_compress is not None:
        events = compress_time(events, opts.time_compress)
    footer = Footer(header.width, opts.footer_colors, opts.annotations) if opts.footer else None
    sampler = Sampler(header, events, opts.time_delta, footer, opts.cursor)
    total_rows = header.height + (footer.height if footer else 0)
    writer = SvgWriter(header.palette, header.width, total_rows, header.cell,
                       loop=opts.loop, hold=opts.hold, dedup=opts.dedup)
    prev = blank_frame(header.width, total_rows)
    last_frame_time = 0.0
    for t, frame in sampler.frames():
        patches = diff_frames(prev, frame, opts.gap, opts.full_threshold)
        if patches:
            writer.add_frame(t, patches)
            last_frame_time = t
        prev = frame
    # The loop must outlast the last drawn frame, which may be the footer's
    # bold revert after the last recorded event.
    duration = max(sampler.end_time, last_frame_time) + opts.hold
    return writer.to_string(duration if opts.loop else None)


def render_cast(path: str | Path, opts: RenderOptions) -> str:
    header, events = read(path)
    return render_events(header, events, opts)
