#!/usr/bin/env bash
# Download one underwater video transect of the catalog below: diver-swum reef
# transects from public NOAA NCEI archives.
#
# Usage: ./01-fetch-transect.sh [transect-key]
#        ./01-fetch-transect.sh --list   (TSV: key, lat, lon, name, remote path)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="https://www.ncei.noaa.gov/data/oceans/archive/arc0120/0172858/1.1/data/0-data/Video_Transect_from_2017-02-03_to_2017-02-08/Video_Transect_from_2017-02-03_to_2017-02-08"

# Catalog: key, site position, map name and file, as a path in the Hawaii
# accession (NCEI 0172858, west Hawaii Island, Feb 2017) or a full URL for
# other archives.
#
# Hawaii: the positions come from the accession's own metadata ("Hawaii Fish Video
# Metadata.docx", degrees and decimal minutes, ~2 m), one per site: transects of
# a site share it. Chosen for clear water and full-length swims (10-12 min,
# ~100 m and more along the tape); Site 5 is left out (murky, three transects
# in one 20 min file). The full inventory (27 files, 0.2-1.7 GB each, 7 sites)
# is browsable by opening $BASE in a browser.
#
# Stetson Bank (NCEI 0239376, Flower Garden Banks National Marine Sanctuary,
# Gulf of Mexico, Jul 2018): permanent 100 m transects, HD camera held at a
# constant height above the line. Each position is the midpoint of the
# transect's start and end points from the accession's video readme;
# transect 3 was filmed in two files.
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
stetson-transect2	28.166063	-94.297603	Stetson Bank, Gulf of Mexico — transect 2	https://www.ncei.noaa.gov/data/oceans/archive/arc0189/0239376/1.1/data/0-data/2018/RAW data/2018 Video Transects/20180717 Transect 2.mp4
stetson-transect3a	28.16595	-94.29635	Stetson Bank, Gulf of Mexico — transect 3 (first part)	https://www.ncei.noaa.gov/data/oceans/archive/arc0189/0239376/1.1/data/0-data/2018/RAW data/2018 Video Transects/20180717 Transect 3a.mp4
stetson-transect3b	28.16595	-94.29635	Stetson Bank, Gulf of Mexico — transect 3 (second part)	https://www.ncei.noaa.gov/data/oceans/archive/arc0189/0239376/1.1/data/0-data/2018/RAW data/2018 Video Transects/20180717 Transect 3b.mp4
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

case "$REMOTE" in
  https://*) URL="$REMOTE" ;;
  *) URL="$BASE/$REMOTE" ;;
esac
# NOAA's filenames contain spaces; only those need percent-encoding.
URL="$(printf '%s' "$URL" | sed 's/ /%20/g')"

echo "Downloading $KEY ..."
# Resume the partial file and retry on any error: the archive server sometimes
# resets or stalls the connection partway through these 1 GB files; a transfer
# under 1 KB/s for a minute counts as stalled.
curl -fL -C - --retry 10 --retry-all-errors --speed-limit 1024 --speed-time 60 --progress-bar -o "$DEST.part" "$URL"
mv "$DEST.part" "$DEST"
echo "Saved to $DEST"
