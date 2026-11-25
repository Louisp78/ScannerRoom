#!/usr/bin/env bash
# Run one pre-processing variant end to end on a transect excerpt and keep
# everything: frames, reconstruction, exported cloud, metrics and renders.
#
# Usage: ./run.sh <transect-key> <variant>     (variants: see the pre-processing script)
# Env:   START (default 0), DURATION (default 20), FPS (default 3), seconds / fps
#        SEED (control-noise seed; when set, the run folder gets a -seedN suffix)
# Output: out/experiments/<key>-<start>s-<duration>s/<variant>/
#   frames/ frames.json   pre-processed input frames and their sidecar
#   recon.npz             LingBot-Map output (reconstruct.py)
#   web/                  cloud.ply + path.json (export-web.py, default settings)
#   metrics.json          scores (metrics.py), render.png, sample.jpg
#   log.txt               output of every step
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY="$1"
VARIANT="$2"
START="${START:-0}"
DURATION="${DURATION:-20}"
FPS="${FPS:-3}"
SEED="${SEED:-}"
RUN="$ROOT/out/experiments/$KEY-${START}s-${DURATION}s/$VARIANT${SEED:+-seed$SEED}"
ENHANCE="$ROOT/vendor/.venv-enhance/bin/python"
LINGBOT="$ROOT/vendor/.venv-lingbot/bin/python"

mkdir -p "$RUN"
exec > >(tee "$RUN/log.txt") 2>&1
echo "== $KEY $VARIANT ($START s + $DURATION s at $FPS fps) $(date '+%F %T')"

"$ENHANCE" "$ROOT/experiments/preprocess.py" "$ROOT/transects/$KEY.mp4" "$RUN/frames" "$VARIANT" \
  --start "$START" --duration "$DURATION" --fps "$FPS" --seed "${SEED:-0}"

(cd "$ROOT/vendor/mlx_lingbot-map" && "$LINGBOT" "$ROOT/scripts/reconstruct.py" "$RUN/frames" "$RUN/recon.npz")

# Default export settings, the same for every variant.
"$LINGBOT" -I "$ROOT/scripts/export-web.py" "$RUN/recon.npz" "$RUN/frames.json" "$RUN/web"

"$LINGBOT" -I "$ROOT/experiments/metrics.py" "$RUN"
