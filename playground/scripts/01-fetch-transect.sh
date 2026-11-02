#!/usr/bin/env bash
# Download one underwater video transect from NOAA NCEI accession 0172858
# (diver-swum coral reef transects, west coast of Hawaii Island, Feb 2017).
#
# Usage: ./01-fetch-transect.sh [transect-key]
#        ./01-fetch-transect.sh --list
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="https://www.ncei.noaa.gov/data/oceans/archive/arc0120/0172858/1.1/data/0-data/Video_Transect_from_2017-02-03_to_2017-02-08/Video_Transect_from_2017-02-03_to_2017-02-08"

# Shortlist of the lightest transects. The full inventory (27 files, 0.2-1.7 GB
# each, 7 sites) is browsable by opening $BASE in a browser.
remote_path_for() {
  case "$1" in
    site3-transect2-south-return)
      echo "Site 3/Old Kona Site 3 2017-02-05 Transect 2 South Leg Return full.MP4" ;;
    site3-transect2-south-forward)
      echo "Site 3/Old Kona Site 3 2017-02-05 Transect 2 South Leg Forward and some return.MP4" ;;
    site3-transect2-north)
      echo "Site 3/Old Kona Site 3 2017-02-05 Transect 2 North Only.MP4" ;;
    site6-transect1)
      echo "Site 6/Mahukona Site 6 2017-02-04 Transect 1.MP4" ;;
    *) return 1 ;;
  esac
}

KEYS="site3-transect2-south-return site3-transect2-south-forward site3-transect2-north site6-transect1"

if [ "${1:-}" = "--list" ]; then
  for k in $KEYS; do printf '%-32s %s\n' "$k" "$(remote_path_for "$k")"; done
  exit 0
fi

KEY="${1:-site3-transect2-south-return}"
REMOTE="$(remote_path_for "$KEY")" || {
  echo "Unknown transect key: $KEY" >&2
  echo "Available: $KEYS" >&2
  exit 1
}

DEST="$ROOT/transects/$KEY.mp4"
mkdir -p "$ROOT/transects"

if [ -s "$DEST" ]; then
  echo "Already downloaded: $DEST"
  exit 0
fi

# NOAA's filenames contain spaces; only those need percent-encoding.
ENCODED="$(printf '%s' "$REMOTE" | sed 's/ /%20/g')"

echo "Downloading $KEY ..."
curl -fL --retry 3 --progress-bar -o "$DEST.part" "$BASE/$ENCODED"
mv "$DEST.part" "$DEST"
echo "Saved to $DEST"
