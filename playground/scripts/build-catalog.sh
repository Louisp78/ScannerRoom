#!/usr/bin/env bash
# Build transects of the fetch step's catalog end to end, one at a time,
# and put them on the map (site catalog).
#
# Strictly sequential: a full-length transect takes ~1000 frames, the
# reconstruction alone fills most of the RAM and the GPU, and the intermediates
# (source video, frames, .npz archive) weigh 3-4 GB. They are deleted once the
# transect is exported, so the disk only ever holds one transect's worth.
# A failing transect is logged and skipped; the others still get built, and its
# reconstruction is kept so that rerunning the key only redoes the export.
#
# Usage: ./build-catalog.sh [transect-key ...]   (default: the whole catalog)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SITES="$ROOT/../src/shared/sites.json"
KEYS=("$@")
[ ${#KEYS[@]} -gt 0 ] || KEYS=($("$HERE/01-fetch-transect.sh" --list | cut -f1))

# Adds the site to the map, or updates its name and position.
register() {
  "$HERE/01-fetch-transect.sh" --list | awk -F'\t' -v k="$1" '$1 == k' |
    python3 -I -c '
import json, sys
key, lat, lon, name, _ = sys.stdin.read().rstrip("\n").split("\t")
path = sys.argv[1]
sites = json.load(open(path))
site = {"transectKey": key, "name": name, "lat": float(lat), "lon": float(lon)}
keys = [s["transectKey"] for s in sites]
# An updated site keeps its place on the map list.
if key in keys:
    sites[keys.index(key)] = site
else:
    sites.append(site)
open(path, "w").write(json.dumps(sites, indent=2, ensure_ascii=False) + "\n")
' "$SITES"
}

failed=()
for key in "${KEYS[@]}"; do
  echo "=== $key ($(date '+%H:%M'))"
  npz="$ROOT/out/lingbot/$key.npz"
  # A reconstruction kept from a failed export is reused (with its frames): only the export reruns.
  if [ -s "$npz" ] && [ -s "$ROOT/frames/$key.json" ]; then
    reconstruct() { echo "Reusing $npz"; }
  else
    # Frames stay until the export, which takes its fine depth and colours from them.
    reconstruct() {
      "$HERE/02-extract-frames.sh" "$key" && "$HERE/03-reconstruct.sh" "$key"
    }
  fi
  # A cleaned video replaces the original (02-extract-frames.sh), so the
  # original is only downloaded when there is none.
  if { [ -s "$ROOT/transects/$key-clean.mp4" ] || "$HERE/01-fetch-transect.sh" "$key"; } && reconstruct && "$HERE/04-export-web.sh" "$key" &&
    register "$key"; then
    echo "=== $key done ($(date '+%H:%M'))"
    # A cleaned video is kept: it is the result of a review, not a download.
    rm -rf "$ROOT/transects/$key.mp4" "$ROOT/frames/$key" "$ROOT/frames/$key.json" "$npz"
  else
    # The video, frames, sidecar and .npz stay (~3-5 GB), so a fixed export
    # does not redo ~30 min of inference and still gets its fine depth.
    echo "=== $key FAILED ($(date '+%H:%M'))"
    failed+=("$key")
  fi
done

[ ${#failed[@]} -eq 0 ] || { echo "Failed: ${failed[*]}" >&2; exit 1; }
echo "All built."
