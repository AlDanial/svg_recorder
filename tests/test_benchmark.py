"""Integration test over the real tdb TUI recording in tests/benchmark.cast."""

from pathlib import Path

from svg_recorder.render import RenderOptions, render_cast
from svg_recorder.svgwriter import check_self_contained

CAST = Path(__file__).parent / "benchmark.cast"


def test_benchmark_cast_renders_small_and_self_contained():
    svg = render_cast(CAST, RenderOptions())
    assert check_self_contained(svg) == []
    assert len(svg.encode("utf-8")) < 200_000
    assert '<use href="#p' in svg          # repeated patch bodies are deduped
