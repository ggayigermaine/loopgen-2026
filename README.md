# loopgen

Turn a long video into the kind of tiny, looping "motion flyer" preview you
see on event sites like posh.vip — muted, short, heavily compressed. It's
almost always a short `<video autoplay muted loop>` (or an animated WebP),
not a GIF and not the full clip. This tool generates and compares those
outputs from your own footage so you can see the size/quality tradeoffs
yourself.

Ships two ways to use it:
- **CLI** (`loopgen.py`) — scriptable, good for batch work
- **Browser GUI** (`loopgen_gui.py`) — drag a file in, tweak sliders, compare formats visually

Both call the same tested encoding logic in `loopcore.py`, so results are identical either way.

---

## Requirements

- **Python 3.9+**
- **ffmpeg**, on your PATH, built with `libx264`, `libx265`, `libwebp_anim`, and either `libsvtav1` or `libaom-av1`
  - Check with: `ffmpeg -encoders | grep -iE "libx264|libx265|libwebp_anim|svtav1|libaom"`
- **Flask** (GUI only) — `pip install flask`

---

## Install

```bash
# 1. Get ffmpeg on PATH (see OS-specific notes below if this fails)
ffmpeg -version

# 2. Install the one Python dependency needed for the GUI
pip install flask

# 3. You're ready — no other setup
```

### Installing ffmpeg

**Windows** (PowerShell, no admin needed):
```powershell
winget install --id=Gyan.FFmpeg
```
Then **fully close and reopen your terminal** — see [Windows PATH troubleshooting](#windows-path-troubleshooting) below if `ffmpeg -version` still isn't found afterward.

**macOS**:
```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu)**:
```bash
sudo apt install ffmpeg
```

---

## Usage — CLI

```bash
# Quick run with sensible defaults (3s loop, middle of the clip, mp4+hevc+webp)
python3 loopgen.py input.mp4

# Custom start time, loop length, frame rate, and width
python3 loopgen.py input.mp4 --start 12 --duration 3 --fps 15 --width 480

# Pick specific formats and quality
python3 loopgen.py input.mp4 --formats mp4,webp,av1 --crf 28

# Run a full comparison sweep (4 formats × 2 quality presets) and print a size table
python3 loopgen.py input.mp4 --compare
```

**Flags:**

| Flag | Default | Meaning |
|---|---|---|
| `--start` | middle of clip | Loop start offset, in seconds |
| `--duration` | `3.0` | Loop length, in seconds |
| `--fps` | `15` | Output frame rate |
| `--width` | `480` | Output width in px (height scales automatically) |
| `--crf` | `30` | Quality vs. size — lower is higher quality/bigger file |
| `--formats` | `mp4,hevc,webp` | Comma list from `mp4`, `hevc`, `av1`, `webp` |
| `--outdir` | `loopgen_out` | Where output files are written |
| `--compare` | off | Ignores `--formats`/`--crf`, runs a fixed 8-preset sweep instead |

Output is a sorted table (smallest file first) plus the file paths.

---

## Usage — GUI

```bash
python3 loopgen_gui.py
```

Then open **http://127.0.0.1:5001** in your browser.

1. Drag a video in, or click to browse
2. Adjust the loop window (start / duration), frame rate, width, and quality with the sliders
3. Toggle which formats to test (mp4 / hevc / av1 / webp)
4. **Generate loop** — encodes just your selected settings
5. **Compare everything** — runs all 4 formats × 2 quality presets and shows every result with an inline playable preview, sorted smallest-first

Nothing leaves your machine — it's a local Flask dev server, meant for personal use on your own computer, not for deploying publicly as-is.

---

## Project structure

```
loopgen/
├── loopcore.py       # Shared ffmpeg encoding logic (used by both CLI and GUI)
├── loopgen.py         # Command-line interface
├── loopgen_gui.py      # Flask web server (backend for the GUI)
├── templates/
│   └── index.html    # GUI frontend
├── uploads/           # GUI: uploaded source videos land here (gitignored/empty in repo)
└── outputs/           # GUI: generated previews + thumbnails land here
```

---

## How it decides format sizes

Roughly, for the same visual loop:
- **h.264 / h.265 (mp4/hevc)** — smallest, best quality per byte. This is almost certainly what real flyer sites use, wrapped in a muted autoplay `<video>` tag styled to look like an image.
- **AV1** — similar size to h.265, sometimes smaller, but much slower to encode.
- **Animated WebP** — noticeably bigger (often 3–5x) for the same loop, because per-frame image compression can't exploit temporal redundancy the way video codecs do. Use it only when you specifically need a real *image* file (no `<video>` tag) rather than a video-styled-as-an-image.

---

## Windows PATH troubleshooting

If `winget install --id=Gyan.FFmpeg` succeeds but `ffmpeg -version` still says
*"not recognized"* afterward, it's almost always one of these:

**1. You didn't fully restart the terminal.**
PowerShell reads `PATH` once at startup. Editing it (even permanently, via
System Properties or `[Environment]::SetEnvironmentVariable`) does not affect
a shell that's already running. You must **fully close the window** (not a
new tab — some terminal apps share environment state across tabs, or restore
old sessions on reopen) and open a genuinely new one.

**2. Verify the fix actually landed**, in a fresh window:
```powershell
$env:Path -split ';' | Select-String 'ffmpeg'
```
If this is empty, PATH wasn't updated (or this isn't really a fresh process).
If it shows the ffmpeg folder, `ffmpeg -version` should now work.

**3. Find where winget actually installed it**, if you're not sure:
```powershell
Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
```

**4. Add it to your permanent User PATH** (no admin rights needed):
```powershell
$ffmpegExe = Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
$ffmpegDir = Split-Path $ffmpegExe -Parent
$current = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = $current -split ';' | Where-Object { $_ -ne '' -and $_ -notmatch 'ffmpeg' }
$parts += $ffmpegDir
[Environment]::SetEnvironmentVariable("Path", ($parts -join ';'), "User")
```
This also de-duplicates any previous ffmpeg entries before adding a clean one.
Then fully close and reopen your terminal and re-check with `ffmpeg -version`.

**5. Still failing after a genuine restart?** Check for zombie sessions:
```powershell
Get-Process | Where-Object { $_.ProcessName -match 'powershell|pwsh|WindowsTerminal' } | Select-Object Id, ProcessName, StartTime
```
If your terminal app is configured to "restore previous session" on launch,
it may be reopening an old process rather than spawning a truly new one —
check your terminal's settings for that option and disable it, at least
temporarily, to confirm.

You can also check the **System** PATH (separate from User PATH) if User PATH
looks correct but it's still not resolving:
```powershell
[Environment]::GetEnvironmentVariable("Path", "Machine")
```

---

## Notes

- All encodes are muted (`-an`) — these are meant to be silent background loops, matching how flyer sites actually use them.
- The GUI caps uploads at 500MB by default (`MAX_CONTENT_LENGTH` in `loopgen_gui.py`) — raise it there if you need to work with bigger source files.
- `--compare` / "Compare everything" is the most useful mode for actually deciding what to ship — it removes the guesswork of picking a single CRF/format up front.
