#!/usr/bin/env bash
# Turn a LingBot-Map reconstruction into what the Vue viewer loads:
# a cleaned, web-sized point cloud, the diver's timed camera path and a
# web-sized copy of the video, shown in a small window during the traveling.
#
# Usage: ./04-export-web.sh [transect-key]
# Env:   CONF (default 1.05, depth-confidence threshold),
#        PATH_SMOOTH / HEADING_SMOOTH (default 1.0 / 1.5, seconds of video),
#        MAX_POINTS (default 2000000, web budget of the overview cloud),
#        DETAIL_POINTS_PER_SECOND (default 250000, detail tiles budget per second of video)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY="${1:-site3-transect2-south-return}"
SRC="$ROOT/out/lingbot/$KEY.npz"
META="$ROOT/frames/$KEY.json"
VIDEO="$ROOT/transects/$KEY.mp4"
DEST="$ROOT/../public/transects/$KEY"
PY="$ROOT/vendor/.venv-lingbot/bin/python"

[ -s "$SRC" ] || { echo "Missing $SRC — run 03-reconstruct.sh first." >&2; exit 1; }
[ -s "$VIDEO" ] || { echo "Missing $VIDEO — run 01-fetch-transect.sh first." >&2; exit 1; }
[ -s "$META" ] || { echo "Missing $META — rerun 02-extract-frames.sh." >&2; exit 1; }

# The source frames give the cloud its fine depth and full-resolution colours.
FRAMES="$ROOT/frames/$KEY"
if [ -n "$(ls "$FRAMES"/*.jpg 2>/dev/null | head -1)" ]; then
  FRAMES_ARG=(--frames "$FRAMES")
else
  echo "No frames in $FRAMES: exporting at the model's resolution (rerun 02-extract-frames.sh for full detail)." >&2
  FRAMES_ARG=()
fi

"$PY" -I "$ROOT/scripts/export-web.py" "$SRC" "$META" "$DEST" "${FRAMES_ARG[@]}" \
  --conf "${CONF:-1.05}" \
  --path-smooth "${PATH_SMOOTH:-1.0}" --heading-smooth "${HEADING_SMOOTH:-1.5}" \
  --max-points "${MAX_POINTS:-2000000}" --detail-points-per-second "${DETAIL_POINTS_PER_SECOND:-250000}"

# Same timeline as the source (path.json times stay valid), small and muted:
# it only plays in a thumbnail. faststart lets the browser seek before the end
# of the download.
ffmpeg -y -loglevel error -i "$VIDEO" -an -vf scale=-2:360 \
  -c:v libx264 -preset slow -crf 30 -pix_fmt yuv420p -movflags +faststart \
  "$DEST/$KEY.mp4"
echo "saved $DEST/$KEY.mp4 ($(du -h "$DEST/$KEY.mp4" | cut -f1))"
