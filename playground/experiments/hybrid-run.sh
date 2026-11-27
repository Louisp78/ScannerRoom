#!/usr/bin/env bash
# Hybrid SfM + LingBot-Map on one transect excerpt, end to end: the LingBot
# baseline bench run, SfM along the LingBot path, then the hybrid run,
# each exported and scored like any bench run.
#
# Usage: START=28 DURATION=32 ./hybrid-run.sh <transect-key>
# Output: out/experiments/<key>-<start>s-<duration>s/{baseline,hybrid}/
#         and baseline/sfm/ (SfM model, probe.png)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY="$1"
START="${START:-0}"
DURATION="${DURATION:-20}"
SET="$ROOT/out/experiments/$KEY-${START}s-${DURATION}s"
SFM="$ROOT/vendor/.venv-sfm/bin/python"
LINGBOT="$ROOT/vendor/.venv-lingbot/bin/python"
cd "$ROOT/experiments"

[ -s "$SET/baseline/metrics.json" ] || START="$START" DURATION="$DURATION" ./run.sh "$KEY" baseline > /dev/null
echo "baseline $(cat "$SET/baseline/metrics.json" | tr -d '\n ')"

# PyTorch and pycolmap load clashing OpenMP runtimes: matching runs alone,
# with the duplicate tolerated.
KMP_DUPLICATE_LIB_OK=TRUE "$SFM" -I sfm_probe.py match "$SET/baseline" > /dev/null 2>&1
"$SFM" -I sfm_probe.py map "$SET/baseline" > "$SET/baseline/sfm/map.log" 2>&1
echo "sfm $(tail -1 "$SET/baseline/sfm/map.log")"

"$SFM" -I hybrid.py "$SET/baseline" "$SET/baseline/sfm" hybrid > /dev/null
"$LINGBOT" -I "$ROOT/scripts/export-web.py" "$SET/hybrid/recon.npz" "$SET/hybrid/frames.json" "$SET/hybrid/web" \
  > "$SET/hybrid/log.txt" 2>&1
echo "hybrid $(tr -d '\n ' < "$SET/hybrid/hybrid.json") $("$LINGBOT" -I metrics.py "$SET/hybrid" | tail -1)"
