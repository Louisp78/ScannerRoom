#!/usr/bin/env bash
# Publish every run of an experiment set to the LOCAL app, as transects named
# "<transect> · exp <run>", so they can be opened one after the other in the
# viewer and compared.
#
# Usage: ./show-in-ui.sh <transect-key> [set]     e.g. ./show-in-ui.sh tab-south
#        ./show-in-ui.sh --remove <transect-key>  (undo)
#   set defaults to <transect-key>-0s-20s (a folder of out/experiments/).
#
# For each run: public/transects/<key>-exp-<run>/ (cloud, path, video copied
# from the transect's own web folder), a map point in src/sites.json next to
# the transect's site (offset ~30 m per run so every point stays clickable)
# and a showcase row in the local database, so the viewer opens it without
# signing in. Local comparison only: the folders are ignored by git, and the
# sites.json entries must not be committed (--remove takes them out).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NODE="${NODE:-$HOME/.nvm/versions/node/v$(cat "$ROOT/.nvmrc" | tr -d v)/bin/node}"

if [ "${1:-}" = "--remove" ]; then
  KEY="$2"
  rm -rf "$ROOT/public/transects/$KEY-exp-"*
  python3 - "$ROOT/src/sites.json" "$KEY-exp-" <<'PY'
import json, sys
p, prefix = sys.argv[1:]
sites = [s for s in json.load(open(p)) if not s["transectKey"].startswith(prefix)]
open(p, "w").write(json.dumps(sites, indent=2, ensure_ascii=False) + "\n")
PY
  echo "Removed $KEY-exp-* from public/transects and src/sites.json (database rows are kept, harmless)."
  exit 0
fi

KEY="$1"
SET="$ROOT/playground/out/experiments/${2:-$KEY-0s-20s}"
VIDEO="$ROOT/public/transects/$KEY/$KEY.mp4"
[ -d "$SET" ] || { echo "No experiment set at $SET" >&2; exit 1; }
[ -s "$VIDEO" ] || { echo "Missing $VIDEO (the transect's web video)." >&2; exit 1; }

KEYS=()
for run in "$SET"/*/; do
  run="$(basename "$run")"
  [ -s "$SET/$run/web/cloud.ply" ] || continue
  # Transect keys are lowercase words joined by '-'. A set other than the
  # default one adds its excerpt (e.g. 28s-32s), so several excerpts of one
  # transect can be on the map at once.
  tag="$run"
  [ -z "${2:-}" ] || tag="${2#"$KEY"-}-$run"
  key="$KEY-exp-$(printf '%s' "$tag" | tr '+_.' '---' | tr -cd 'a-z0-9-')"
  dest="$ROOT/public/transects/$key"
  mkdir -p "$dest"
  rm -rf "$dest/tiles"
  cp "$SET/$run/web/cloud.ply" "$SET/$run/web/path.json" "$dest/"
  # Detail tiles, when the export wrote any.
  [ -d "$SET/$run/web/tiles" ] && cp -R "$SET/$run/web/tiles" "$dest/"
  cp "$VIDEO" "$dest/"
  KEYS+=("$key")
  echo "$run -> $dest"
done

python3 - "$ROOT/src/sites.json" "$KEY" "${KEYS[@]}" <<'PY'
import json, sys
p, base, *keys = sys.argv[1:]
sites = json.load(open(p))
origin = next(s for s in sites if s["transectKey"] == base)
sites = [s for s in sites if s["transectKey"] not in keys]
for i, key in enumerate(keys, 1):
    run = key[len(base) + len("-exp-"):]  # excerpt and run
    sites.append({"transectKey": key, "name": f"{origin['name']} · exp {run}",
                  "lat": origin["lat"], "lon": round(origin["lon"] + 0.0003 * i, 6)})
open(p, "w").write(json.dumps(sites, indent=2, ensure_ascii=False) + "\n")
PY

(cd "$ROOT/api" && "$NODE" --env-file=.env scripts/register-transect.ts "${KEYS[@]}" --showcase > /dev/null)
echo "${#KEYS[@]} runs added to the map and registered as showcases."
