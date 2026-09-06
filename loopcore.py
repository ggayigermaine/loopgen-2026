"""
loopcore.py — shared encoding logic for loopgen (CLI) and loopgen_gui (Flask app).

Turns a long source video into a short, tiny, looping preview using ffmpeg,
in mp4 (h264), hevc (h265), av1, or animated webp.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        tail = (result.stdout or "")[-2000:]
        raise RuntimeError(f"Command failed ({' '.join(cmd)}):\n{tail}")
    return result


def probe_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
    result = run(cmd)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


@dataclass
class LoopSpec:
    fmt: str                 # "mp4" (h264), "hevc" (h265), "av1", "webp"
    fps: int = 15
    width: int = 480
    crf: int = 30
    start: float = 0.0
    duration: float = 3.0
    label: str = ""

    def out_suffix(self) -> str:
        return "webp" if self.fmt == "webp" else "mp4"


def build_filter(width: int, fps: int) -> str:
    return f"fps={fps},scale={width}:-2:flags=lanczos"


def encode(input_path: Path, out_path: Path, spec: LoopSpec) -> None:
    vf = build_filter(spec.width, spec.fps)

    base = [
        "ffmpeg", "-y",
        "-ss", str(spec.start),
        "-t", str(spec.duration),
        "-i", str(input_path),
        "-vf", vf,
        "-an",
    ]

    if spec.fmt == "mp4":
        cmd = base + [
            "-c:v", "libx264", "-preset", "veryslow", "-crf", str(spec.crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path),
        ]
    elif spec.fmt == "hevc":
        cmd = base + [
            "-c:v", "libx265", "-preset", "slow", "-crf", str(spec.crf),
            "-tag:v", "hvc1", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path),
        ]
    elif spec.fmt == "av1":
        cmd = base + [
            "-c:v", "libsvtav1", "-crf", str(spec.crf), "-preset", "6",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path),
        ]
    elif spec.fmt == "webp":
        quality = max(0, min(100, 100 - spec.crf * 2))
        cmd = base + [
            "-loop", "0", "-c:v", "libwebp_anim", "-lossless", "0",
            "-q:v", str(quality), "-compression_level", "6", str(out_path),
        ]
    else:
        raise ValueError(f"Unknown format: {spec.fmt}")

    run(cmd)


def make_thumbnail(input_path: Path, out_path: Path, at_second: float) -> None:
    """Grab a single JPEG frame, used as a lightweight preview before encoding."""
    cmd = [
        "ffmpeg", "-y", "-ss", str(at_second), "-i", str(input_path),
        "-frames:v", "1", "-vf", "scale=480:-2", str(out_path),
    ]
    run(cmd)
