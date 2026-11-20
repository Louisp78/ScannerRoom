#!/usr/bin/env bash
# Publishes exported transects to the VPS. Transect data is not in the
# repository: each public/transects/<key>/ folder is uploaded to
# ~/scannerroom/transects/<key>/ on the VPS (mounted into the site container by
# deploy/vps.sh), then registered in the database.
#
# Usage: deploy/publish-transect.sh <key>...
#
# Only changed files are sent, and files removed locally are removed on the VPS,
# so re-publishing after a re-export is cheap. Publish the data before pushing
# the src/sites.json entry that points to it. The VPS is reached through the ssh
# host $SCANNERROOM_SSH (default: louisplace-app).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${SCANNERROOM_SSH:-louisplace-app}"

if [ $# -eq 0 ]; then
  echo "Usage: $0 <key>..." >&2
  exit 1
fi
# Same key format as the API (register-transect.ts); it also keeps the keys
# safe to pass through the remote shell below.
for key in "$@"; do
  if [[ ! "$key" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    echo "Invalid transect key: $key" >&2
    exit 1
  fi
  if [ ! -d "$ROOT/public/transects/$key" ]; then
    echo "Not exported: public/transects/$key/" >&2
    exit 1
  fi
done

for key in "$@"; do
  echo "Uploading $key..."
  # --delay-updates moves the new files into place at the end, so viewers see
  # a mix of old and new files only for that short moment.
  rsync -az --delete --delay-updates "$ROOT/public/transects/$key/" "$HOST:scannerroom/transects/$key/"
done

# Already registered transects are left untouched (owner, showcase flag).
ssh "$HOST" docker exec scannerroom-api node scripts/register-transect.ts "$@"
