"""Recording to SVG: sample, diff, write."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .annotations import Annotations
from .asciicast import Event, Header, read
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


def render_events(header: Header, events: list[Event], opts: RenderOptions) -> str:
    footer = Footer(header.width, opts.footer_colors, opts.annotations) if opts.footer else None
    sampler = Sampler(header, events, opts.time_delta, footer, opts.cursor)
    total_rows = header.height + (footer.height if footer else 0)
    writer = SvgWriter(header.palette, header.width, total_rows, header.cell,
                       loop=opts.loop, hold=opts.hold, dedup=opts.dedup)
    prev = blank_frame(header.width, total_rows)
    for t, frame in sampler.frames():
        patches = diff_frames(prev, frame, opts.gap, opts.full_threshold)
        if patches:
            writer.add_frame(t, patches)
        prev = frame
    return writer.to_string(sampler.end_time + opts.hold if opts.loop else None)


def render_cast(path: str | Path, opts: RenderOptions) -> str:
    header, events = read(path)
    return render_events(header, events, opts)
