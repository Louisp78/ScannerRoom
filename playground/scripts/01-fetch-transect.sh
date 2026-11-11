#!/usr/bin/env bash
# Download one underwater video transect from NOAA NCEI accession 0172858
# (diver-swum coral reef transects, west coast of Hawaii Island, Feb 2017).
#
# Usage: ./01-fetch-transect.sh [transect-key]
#        ./01-fetch-transect.sh --list   (TSV: key, lat, lon, name, remote path)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="https://www.ncei.noaa.gov/data/oceans/archive/arc0120/0172858/1.1/data/0-data/Video_Transect_from_2017-02-03_to_2017-02-08/Video_Transect_from_2017-02-03_to_2017-02-08"

# Catalog: key, site position, map name and file in the accession. The
# positions come from the accession's own metadata ("Hawaii Fish Video
# Metadata.docx", degrees and decimal minutes, ~2 m), one per site: transects of
# a site share it. Chosen for clear water and full-length swims (10-12 min,
# ~100 m and more along the tape); Site 5 is left out (murky, three transects
# in one 20 min file). The full inventory (27 files, 0.2-1.7 GB each, 7 sites)
# is browsable by opening $BASE in a browser.
CATALOG="$(cat <<'TSV'
site3-transect2-south-return	19.645883	-156.0167	Old Kona, site 3 — transect 2 (south leg return)	Site 3/Old Kona Site 3 2017-02-05 Transect 2 South Leg Return full.MP4
site3-transect2-north	19.645883	-156.0167	Old Kona, site 3 — transect 2 (north leg)	Site 3/Old Kona Site 3 2017-02-05 Transect 2 North Only.MP4
site3-transect3	19.645883	-156.0167	Old Kona, site 3 — transect 3	Site 3/Old Kona Site 3 2017-02-05 Transect 3.MP4
site4-transect1	19.644736	-156.016117	Old Kona, site 4 — transect 1	Site 4/Old Kona Site 4 2017-02-05 Transect 1.MP4
site4-transect2	19.644736	-156.016117	Old Kona, site 4 — transect 2	Site 4/Old Kona Site 4 2017-02-05 Transect 2.MP4
site1-transect1	19.970633	-155.84575	Puakō, site 1 — transect 1	Site 1/Puako Site 1 2017-02-03 Transect 1.MP4
site1-transect4	19.970633	-155.84575	Puakō, site 1 — transect 4	Site 1/Puako Site 1 2017-02-03 Transect 4.MP4
site2-transect1	19.96915	-155.851233	Puakō, site 2 — transect 1	Site 2/Puako Site 2 2017-02-03 Transect 1.MP4
site2-transect2	19.96915	-155.851233	Puakō, site 2 — transect 2	Site 2/Puako Site 2 2017-02-03 Transect 2.MP4
site6-transect1	20.183383	-155.902067	Mahukona, site 6 — transect 1	Site 6/Mahukona Site 6 2017-02-04 Transect 1.MP4
site6-transect2	20.183383	-155.902067	Mahukona, site 6 — transect 2	Site 6/Mahukona Site 6 2017-02-04 Transect 2.MP4
site7-transect2	20.18405	-155.901517	Mahukona, site 7 — transect 2	Site 7/Mahukona Site 7 2017-02-04 Transect 2.MP4
TSV
)"

# Prints the catalog as TSV: key, latitude, longitude, name, remote path.
if [ "${1:-}" = "--list" ]; then
  printf '%s\n' "$CATALOG"
  exit 0
fi

KEY="${1:-site3-transect2-south-return}"
REMOTE="$(printf '%s\n' "$CATALOG" | awk -F'\t' -v k="$KEY" '$1 == k { print $5 }')"
[ -n "$REMOTE" ] || {
  echo "Unknown transect key: $KEY" >&2
  echo "Available: $(printf '%s\n' "$CATALOG" | cut -f1 | tr '\n' ' ')" >&2
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
