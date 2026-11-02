#!/usr/bin/env bash
# Extract a frame sequence from a transect video, sized for Structure-from-Motion.
#
# Photogrammetry needs consecutive frames to overlap heavily (~70-80%). A diver
# swims slowly, so 2 fps is a reasonable starting point; raise FPS if the
# reconstruction fails to register frames, lower it if it is needlessly slow.
#
# Usage: ./02-extract-frames.sh [transect-key]
# Env:   FPS (default 2), START (default 0, seconds), DURATION (default 60, seconds)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY="${1:-site3-transect2-south-return}"
FPS="${FPS:-2}"
START="${START:-0}"
DURATION="${DURATION:-60}"

SRC="$ROOT/transects/$KEY.mp4"
DEST="$ROOT/frames/$KEY"

[ -s "$SRC" ] || { echo "Missing $SRC — run 01-fetch-transect.sh first." >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg not found (brew install ffmpeg)." >&2; exit 1; }

rm -rf "$DEST"
mkdir -p "$DEST"

# -ss before -i seeks by keyframe (fast); -q:v 2 keeps JPEG artefacts low enough
# not to disturb feature matching, at a fraction of PNG's size.
ffmpeg -hide_banner -loglevel warning -stats \
  -ss "$START" -t "$DURATION" -i "$SRC" \
  -vf "fps=$FPS" -q:v 2 \
  "$DEST/frame_%04d.jpg"

# Sidecar next to (not inside) the frame folder, so the reconstruction only sees
# images. 04-export-web.sh uses it to timestamp each frame in the source video.
printf '{"video": "%s", "fps": %s, "start": %s}\n' "$KEY.mp4" "$FPS" "$START" > "$DEST.json"

echo "Extracted $(ls "$DEST" | wc -l | tr -d ' ') frames to $DEST"
