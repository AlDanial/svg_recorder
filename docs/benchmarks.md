# Benchmarks

## Measurement date

2026-09-11 at commit `48801aa`.

## Recording

The benchmark recording, `tests/benchmark.cast`, was recorded headlessly on 2026-09-11 through a pty pair at 120 columns by 36 rows with `TERM=xterm-256color` and the default kitty palette. It contains the tdb session `tdb --replay-quiet --replay-interval 0.5 --replay-tui session.txt` run from `tests/`, with 545 events over about 16 seconds. The recording was not made in a kitty window.

To replace it with a recording made in a kitty window, run from the repository root:

```bash
uv run svg_recorder --keep-recording -o tests/benchmark.svg
```

then in the new shell:

```bash
cd tests
tdb --replay-quiet --replay-interval 0.5 --replay-tui session.txt
exit
```

Delete `tests/benchmark.svg`, keep `tests/benchmark.cast`, and re-run `uv run python tools/sizes.py tests/benchmark.cast`.

## Baseline

termtosvg 1.1.0 installed with `uv tool install termtosvg`.

```bash
termtosvg render tests/benchmark.cast baseline.svg
```

termtosvg output: 2,022,472 bytes raw, 138,572 bytes gzipped.

## Results

Full harness table from `uv run python tools/sizes.py tests/benchmark.cast`:

```
variant           benchmark.cast
default                  176,040
gap0                     206,460
gap4                     177,690
full-never               176,040
full-0.25                195,406
no-dedup                 255,514
no-loop                  171,348
delta-0.1                170,650
footer                   176,797
default+gzip              15,824
```

## Ratios

- Default is **11.5 times smaller** than termtosvg raw (2,022,472 / 176,040 ≈ 11.5×)
- Default is **8.8 times smaller** gzipped (138,572 / 15,824 ≈ 8.8×)

## Observations

- Dedup saves the most: no-dedup is 45% larger than default.
- The gap tolerance of 2 beats 0 by 15% and is within 1% of 4.
- The whole-screen threshold never triggers on this recording: full-never equals default.
- Halving the sample rate saves only 3%.
- The footer costs under 1%.

## Visual check

Snapshots at 3 s and 12 s of playback showed the tdb TUI with aligned columns, correct colors, and box drawing intact. The replay visibly advanced between the snapshots.
