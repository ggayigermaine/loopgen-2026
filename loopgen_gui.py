#!/usr/bin/env python3
"""
loopgen_gui.py — browser GUI for loopgen.

Run:
    python3 loopgen_gui.py

Then open http://127.0.0.1:5001 in your browser. Drag in a video, pick
settings, hit Generate, and compare output sizes with inline previews.

Requires: flask, ffmpeg (with libx264/libx265/libwebp_anim/libsvtav1).
"""

import shutil
import sys
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

from loopcore import LoopSpec, encode, human_size, make_thumbnail, probe_duration

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500MB safety cap

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

# In-memory registry of uploaded sources for this session (fine for a local single-user tool)
SOURCES = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    source_id = uuid.uuid4().hex[:12]
    ext = Path(f.filename).suffix or ".mp4"
    dest = UPLOAD_DIR / f"{source_id}{ext}"
    f.save(dest)

    try:
        duration = probe_duration(dest)
    except Exception as e:
        dest.unlink(missing_ok=True)
        return jsonify({"error": f"Could not read video: {e}"}), 400

    size = dest.stat().st_size
    SOURCES[source_id] = {"path": dest, "duration": duration, "size": size, "name": f.filename}

    thumb_path = OUTPUT_DIR / f"{source_id}_thumb.jpg"
    try:
        make_thumbnail(dest, thumb_path, at_second=min(1.0, duration / 2))
        thumb_url = f"/media/{thumb_path.name}"
    except Exception:
        thumb_url = None

    return jsonify({
        "source_id": source_id,
        "name": f.filename,
        "size": size,
        "size_human": human_size(size),
        "duration": round(duration, 2),
        "thumb_url": thumb_url,
    })


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    source_id = data.get("source_id")
    if source_id not in SOURCES:
        return jsonify({"error": "Unknown source_id — re-upload the file"}), 400

    src = SOURCES[source_id]
    src_path: Path = src["path"]
    src_duration = src["duration"]
    src_size = src["size"]

    start = float(data.get("start", max(0.0, src_duration / 2 - 1.5)))
    duration = float(data.get("duration", 3.0))
    fps = int(data.get("fps", 15))
    width = int(data.get("width", 480))
    crf = int(data.get("crf", 30))
    formats = data.get("formats") or ["mp4", "hevc", "webp"]
    compare = bool(data.get("compare", False))

    start = max(0.0, min(start, max(0.0, src_duration - 0.1)))
    duration = max(0.5, min(duration, src_duration - start, 15.0))

    if compare:
        specs = []
        for fmt in ("mp4", "hevc", "av1", "webp"):
            for f_fps, f_width, f_crf in [(15, 480, 28), (12, 360, 32)]:
                specs.append(LoopSpec(
                    fmt=fmt, fps=f_fps, width=f_width, crf=f_crf,
                    start=start, duration=duration,
                    label=f"{fmt} · {f_fps}fps · {f_width}px · crf{f_crf}",
                ))
    else:
        specs = [
            LoopSpec(
                fmt=fmt, fps=fps, width=width, crf=crf,
                start=start, duration=duration,
                label=f"{fmt} · {fps}fps · {width}px · crf{crf}",
            )
            for fmt in formats
        ]

    results = []
    for spec in specs:
        out_id = uuid.uuid4().hex[:10]
        out_name = f"{out_id}.{spec.out_suffix()}"
        out_path = OUTPUT_DIR / out_name
        try:
            encode(src_path, out_path, spec)
        except RuntimeError as e:
            results.append({"label": spec.label, "fmt": spec.fmt, "error": str(e)[-500:]})
            continue

        out_size = out_path.stat().st_size
        results.append({
            "label": spec.label,
            "fmt": spec.fmt,
            "size": out_size,
            "size_human": human_size(out_size),
            "pct_of_source": round(out_size / src_size * 100, 3),
            "url": f"/media/{out_name}",
        })

    results.sort(key=lambda r: r.get("size", float("inf")))

    return jsonify({
        "start": start,
        "duration": duration,
        "src_size_human": human_size(src_size),
        "results": results,
    })


@app.route("/media/<path:filename>")
def media(filename):
    return send_from_directory(OUTPUT_DIR, filename)


if __name__ == "__main__":
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH. Install it first, then re-run this app.")
    print("loopgen GUI running at http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
