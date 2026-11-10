#!/usr/bin/env bash
# Turn a LingBot-Map reconstruction into what the Vue viewer loads:
# a cleaned, web-sized point cloud, the diver's timed camera path and a
# web-sized copy of the video, shown in a small window during the traveling.
#
# Usage: ./04-export-web.sh [transect-key]
# Env:   CONF (default 1.05, depth-confidence threshold), VOXEL (default 0.01, fraction of median depth),
#        PATH_SMOOTH / HEADING_SMOOTH (default 1.0 / 1.5, seconds of video)
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

"$PY" -I "$ROOT/scripts/export-web.py" "$SRC" "$META" "$DEST" \
  --conf "${CONF:-1.05}" --voxel "${VOXEL:-0.01}" \
  --path-smooth "${PATH_SMOOTH:-1.0}" --heading-smooth "${HEADING_SMOOTH:-1.5}"

# Same timeline as the source (path.json times stay valid), small and muted:
# it only plays in a thumbnail. faststart lets the browser seek before the end
# of the download.
ffmpeg -y -loglevel error -i "$VIDEO" -an -vf scale=-2:360 \
  -c:v libx264 -preset slow -crf 30 -pix_fmt yuv420p -movflags +faststart \
  "$DEST/$KEY.mp4"
echo "saved $DEST/$KEY.mp4 ($(du -h "$DEST/$KEY.mp4" | cut -f1))"
