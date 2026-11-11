#!/usr/bin/env bash
# Extract a frame sequence from a transect video, sized for Structure-from-Motion.
#
# Photogrammetry needs consecutive frames to overlap heavily (~70-80%). A diver
# swims slowly, so 2 fps is a reasonable starting point; raise FPS if the
# reconstruction fails to register frames, lower it if it is needlessly slow.
#
# By default the whole video is kept: the longer the swim, the more reef the 3D
# covers. The frame rate then follows the video's length so the sequence stays
# under LingBot-Map's frame limit (2 fps up to ~8 min, ~1.4 fps for 12 min).
#
# Usage: ./02-extract-frames.sh [transect-key]
# Env:   FPS (default: 2, lowered to fit MAX_FRAMES), START (default 0, seconds),
#        DURATION (default: until the end of the video, seconds)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY="${1:-site3-transect2-south-return}"
START="${START:-0}"
# LingBot-Map's temporal embedding covers 1024 frames; keep a margin.
MAX_FRAMES=1000

SRC="$ROOT/transects/$KEY.mp4"
DEST="$ROOT/frames/$KEY"

[ -s "$SRC" ] || { echo "Missing $SRC — run 01-fetch-transect.sh first." >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg not found (brew install ffmpeg)." >&2; exit 1; }

LENGTH="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC")"
DURATION="${DURATION:-$(awk -v l="$LENGTH" -v s="$START" 'BEGIN { print l - s }')}"
FPS="${FPS:-$(awk -v d="$DURATION" -v m="$MAX_FRAMES" 'BEGIN { f = m / d; printf "%.3f", (f < 2 ? f : 2) }')}"

rm -rf "$DEST"
mkdir -p "$DEST"

# -ss before -i seeks by keyframe (fast); -q:v 2 keeps JPEG artefacts low enough
# not to disturb feature matching, at a fraction of PNG's size.
ffmpeg -hide_banner -loglevel warning -stats \
  -ss "$START" -t "$DURATION" -i "$SRC" \
  -vf "fps=$FPS" -q:v 2 \
  "$DEST/frame_%04d.jpg"

# ffmpeg applies the video's rotation metadata, so phone videos come out as
# portrait frames. LingBot-Map turns portrait frames 90 deg clockwise before
# reconstructing; 04-export-web.sh needs to know, to stand the scene back up.
IFS=x read -r W H < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height \
  -of csv=p=0:s=x "$DEST/frame_0001.jpg")
PORTRAIT=$([ "$H" -gt "$W" ] && echo true || echo false)

# Sidecar next to (not inside) the frame folder, so the reconstruction only sees
# images. 04-export-web.sh uses it to timestamp each frame in the source video.
printf '{"video": "%s", "fps": %s, "start": %s, "length": %s, "portrait": %s}\n' \
  "$KEY.mp4" "$FPS" "$START" "$LENGTH" "$PORTRAIT" > "$DEST.json"

echo "Extracted $(ls "$DEST" | wc -l | tr -d ' ') frames at $FPS fps to $DEST"
