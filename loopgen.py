#!/usr/bin/env python3
"""
loopgen.py — turn a long video into a tiny looping "motion flyer" preview.

This is the trick behind sites like posh.vip showing "moving images" that
are actually short, muted, low-fps, heavily-compressed video or animated
WebP loops — not full videos and not GIFs.

Usage:
    python3 loopgen.py input.mp4
    python3 loopgen.py input.mp4 --start 12 --duration 3 --fps 15 --width 480
    python3 loopgen.py input.mp4 --formats mp4,webp,av1 --crf 30
    python3 loopgen.py input.mp4 --compare   # generates several presets + prints a size table

Also ships a browser GUI — run:
    python3 loopgen_gui.py

Requires: ffmpeg on PATH (with libx264, libx265, libwebp_anim, libaom-av1 or
libsvtav1 built in — check with `ffmpeg -encoders`).
"""

import argparse
import shutil
import sys
from pathlib import Path

from loopcore import LoopSpec, encode, human_size, probe_duration


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help="Source video file (e.g. a 1-min / 200MB clip)")
    parser.add_argument("--outdir", type=Path, default=Path("loopgen_out"), help="Output directory")
    parser.add_argument("--start", type=float, default=None, help="Start offset in seconds (default: middle of clip)")
    parser.add_argument("--duration", type=float, default=3.0, help="Loop length in seconds (default: 3)")
    parser.add_argument("--fps", type=int, default=15, help="Output frame rate (default: 15)")
    parser.add_argument("--width", type=int, default=480, help="Output width in px, height auto (default: 480)")
    parser.add_argument("--crf", type=int, default=30, help="Quality/size tradeoff, lower=better/bigger (default: 30)")
    parser.add_argument(
        "--formats", type=str, default="mp4,hevc,webp",
        help="Comma list from: mp4,hevc,av1,webp (default: mp4,hevc,webp)"
    )
    parser.add_argument(
        "--compare", action="store_true",
        help="Ignore --formats/--crf and run a fixed set of presets across all formats, printing a size table"
    )
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH. Install it first.")
    if not args.input.exists():
        sys.exit(f"Input file not found: {args.input}")

    args.outdir.mkdir(parents=True, exist_ok=True)

    src_size = args.input.stat().st_size
    duration = probe_duration(args.input)
    start = args.start if args.start is not None else max(0.0, duration / 2 - args.duration / 2)

    print(f"Source: {args.input.name}  ({human_size(src_size)}, {duration:.1f}s)")
    print(f"Loop window: {start:.1f}s -> {start + args.duration:.1f}s\n")

    if args.compare:
        specs = []
        for fmt in ("mp4", "hevc", "av1", "webp"):
            for fps, width, crf in [(15, 480, 28), (12, 360, 32)]:
                specs.append(LoopSpec(
                    fmt=fmt, fps=fps, width=width, crf=crf,
                    start=start, duration=args.duration,
                    label=f"{fmt}_fps{fps}_w{width}_crf{crf}",
                ))
    else:
        formats = [f.strip() for f in args.formats.split(",") if f.strip()]
        specs = [
            LoopSpec(
                fmt=fmt, fps=args.fps, width=args.width, crf=args.crf,
                start=start, duration=args.duration,
                label=f"{fmt}_fps{args.fps}_w{args.width}_crf{args.crf}",
            )
            for fmt in formats
        ]

    rows = []
    for spec in specs:
        out_path = args.outdir / f"{args.input.stem}_{spec.label}.{spec.out_suffix()}"
        try:
            encode(args.input, out_path, spec)
        except RuntimeError as e:
            print(f"[FAILED] {spec.label}: {e}")
            continue
        out_size = out_path.stat().st_size
        pct = out_size / src_size * 100
        rows.append((spec.label, out_size, pct, out_path))

    if not rows:
        sys.exit("No outputs were generated — check the ffmpeg errors above.")

    rows.sort(key=lambda r: r[1])

    print(f"{'preset':32s} {'size':>10s} {'% of source':>12s}   file")
    print("-" * 80)
    for label, size, pct, path in rows:
        print(f"{label:32s} {human_size(size):>10s} {pct:>11.2f}%   {path}")

    best = rows[0]
    print(f"\nSmallest: {best[0]} -> {human_size(best[1])} ({best[2]:.2f}% of the {human_size(src_size)} source)")


if __name__ == "__main__":
    main()
