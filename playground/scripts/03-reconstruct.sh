#!/usr/bin/env bash
# Reconstruct a frame sequence with LingBot-Map: camera pose + per-pixel depth
# and confidence for every frame, saved as one .npz archive.
#
# Feed-forward model, no feature matching: ~2 s per frame on an M3 Pro.
# Runs reconstruct.py rather than the port's create_map.py, which also writes
# several GB of unused points on full-length transects (see reconstruct.py).
#
# Usage: ./03-reconstruct.sh [transect-key]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY="${1:-site3-transect2-south-return}"
FRAMES="$ROOT/frames/$KEY"
OUT="$ROOT/out/lingbot/$KEY.npz"
PY="$ROOT/vendor/.venv-lingbot/bin/python"

[ -d "$FRAMES" ] || { echo "Missing $FRAMES — run 02-extract-frames.sh first." >&2; exit 1; }
[ -x "$PY" ] || { echo "LingBot-Map not installed — run 00-setup-lingbot.sh first." >&2; exit 1; }

mkdir -p "$(dirname "$OUT")"
# create_map.py resolves checkpoints/ relative to its own folder.
cd "$ROOT/vendor/mlx_lingbot-map"
"$PY" "$ROOT/scripts/reconstruct.py" "$FRAMES" "$OUT"

echo "Reconstruction saved to $OUT"
