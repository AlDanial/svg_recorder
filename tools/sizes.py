#!/usr/bin/env python3
"""Render recordings under several strategy variants and print output sizes.

Usage: uv run python tools/sizes.py tests/benchmark.cast [more.cast ...]
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from svg_recorder.asciicast import read  # noqa: E402
from svg_recorder.render import RenderOptions, render_events  # noqa: E402

VARIANTS = {
    "default": RenderOptions(),
    "gap0": RenderOptions(gap=0),
    "gap4": RenderOptions(gap=4),
    "full-never": RenderOptions(full_threshold=1.01),
    "full-0.25": RenderOptions(full_threshold=0.25),
    "no-dedup": RenderOptions(dedup=False),
    "no-loop": RenderOptions(loop=False),
    "delta-0.1": RenderOptions(time_delta=0.1),
    "footer": RenderOptions(footer=True),
}


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        return 2
    casts = [(Path(p).name, *read(p)) for p in paths]
    width = max(len(n) for n in VARIANTS) + 4
    print("variant".ljust(width) + "".join(name.rjust(18) for name, _, _ in casts))
    for name, opts in VARIANTS.items():
        row = name.ljust(width)
        for _, header, events in casts:
            row += f"{len(render_events(header, events, opts).encode()):>18,}"
        print(row)
    row = "default+gzip".ljust(width)
    for _, header, events in casts:
        row += f"{len(gzip.compress(render_events(header, events, RenderOptions()).encode())):>18,}"
    print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
