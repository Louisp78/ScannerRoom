#!/usr/bin/env bash
# Hybrid SfM + LingBot-Map on one transect excerpt, end to end: the LingBot
# baseline bench run, SfM along the LingBot path, then the hybrid variants,
# each exported and scored like any bench run.
#
# Usage: START=28 DURATION=32 ./hybrid-run.sh <transect-key>
# Output: out/experiments/<key>-<start>s-<duration>s/{baseline,hybrid-depth,hybrid-gate}/
#         and baseline/sfm-raw/ (SfM model, probe.png)
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
KMP_DUPLICATE_LIB_OK=TRUE "$SFM" -I sfm_probe.py match "$SET/baseline" raw > /dev/null 2>&1
"$SFM" -I sfm_probe.py map "$SET/baseline" raw > "$SET/baseline/sfm-raw/map.log" 2>&1
echo "sfm $(tail -1 "$SET/baseline/sfm-raw/map.log")"

for variant in hybrid-depth hybrid-gate; do
  "$SFM" -I hybrid.py "$SET/baseline" "$SET/baseline/sfm-raw" "$variant" > /dev/null
  "$LINGBOT" -I "$ROOT/scripts/export-web.py" "$SET/$variant/recon.npz" "$SET/$variant/frames.json" "$SET/$variant/web" \
    > "$SET/$variant/log.txt" 2>&1
  echo "$variant $(tr -d '\n ' < "$SET/$variant/hybrid.json") $("$LINGBOT" -I metrics.py "$SET/$variant" | tail -1)"
done
