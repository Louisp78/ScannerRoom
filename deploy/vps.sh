#!/usr/bin/env bash
# Builds and (re)starts the ScannerRoom containers on the VPS.
# Run by CI from the uploaded source folder (~/scannerroom/src). Expects the
# secrets below in the environment (passed through by the ssh action).
#
# The VPS native nginx (behind Cloudflare) routes
# scannerroom.louisplace.com -> 127.0.0.1:3001 (the site container). The site
# container proxies /api to the API container; the API and the database only
# live on the internal "scannerroom" docker network.
#
# Transect data is not in the repository: it lives in ~/scannerroom/transects
# (outside the source folder CI wipes), uploaded by deploy/publish-transect.sh,
# and is mounted read-only into the site container.
set -euo pipefail

# Required secrets fail fast; OAuth providers and admins are optional
# (the API disables what is not configured).
: "${DB_SUPERUSER_PASSWORD:?}" "${DATABASE_PASSWORD:?}" "${SESSION_SECRET:?}"
: "${ORCID_CLIENT_ID=}" "${ORCID_CLIENT_SECRET=}"
: "${GOOGLE_CLIENT_ID=}" "${GOOGLE_CLIENT_SECRET=}"
: "${ADMIN_IDENTITIES=}"

cd "$(dirname "$0")/.."
TRANSECTS=~/scannerroom/transects
mkdir -p "$TRANSECTS"
docker network create scannerroom 2>/dev/null || true

# Database: created once, then kept across deploys (volume
# scannerroom-pgdata). No published port. The init script runs only on an
# empty volume; it is copied out of the wiped source folder.
if ! docker inspect scannerroom-db >/dev/null 2>&1; then
  mkdir -p ~/scannerroom/db-init
  cp api/db-init/* ~/scannerroom/db-init/
  docker run -d \
    --name scannerroom-db \
    --network scannerroom \
    --restart always \
    -e POSTGRES_DB=scannerroom \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD="$DB_SUPERUSER_PASSWORD" \
    -e APP_DB_PASSWORD="$DATABASE_PASSWORD" \
    -v scannerroom-pgdata:/var/lib/postgresql/data \
    -v ~/scannerroom/db-init:/docker-entrypoint-initdb.d:ro \
    postgres:17-alpine
fi

# API: secrets go to an env file only the deploy user can read.
(
  umask 077
  cat > ~/scannerroom/api.env <<ENV
DATABASE_URL=postgres://scannerroom_api:${DATABASE_PASSWORD}@scannerroom-db:5432/scannerroom
SESSION_SECRET=${SESSION_SECRET}
PUBLIC_URL=https://scannerroom.louisplace.com
TRUST_PROXY_HOPS=3
ORCID_ISSUER=https://orcid.org
ORCID_CLIENT_ID=${ORCID_CLIENT_ID}
ORCID_CLIENT_SECRET=${ORCID_CLIENT_SECRET}
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
ADMIN_IDENTITIES=${ADMIN_IDENTITIES}
ENV
)
docker build -t scannerroom-api:latest api
docker rm -f scannerroom-api 2>/dev/null || true
# Every published transect folder must exist in the database (its contributor
# and showcase flag live there). Already registered ones are left untouched.
# Run before the API starts so the two never apply migrations concurrently.
keys=$(ls "$TRANSECTS")
if [ -n "$keys" ]; then
  # shellcheck disable=SC2086 # one argument per key
  docker run --rm \
    --network scannerroom \
    --env-file ~/scannerroom/api.env \
    scannerroom-api:latest \
    node scripts/register-transect.ts $keys
fi
docker run -d \
  --name scannerroom-api \
  --network scannerroom \
  --restart always \
  --env-file ~/scannerroom/api.env \
  scannerroom-api:latest

# Site: the static bundle plus the nginx routing /api and guarding the
# transect data files, mounted from the VPS.
docker build -t scannerroom:latest .
docker rm -f scannerroom 2>/dev/null || true
docker run -d \
  --name scannerroom \
  --network scannerroom \
  --restart always \
  -p 127.0.0.1:3001:80 \
  -v "$TRANSECTS":/usr/share/nginx/html/transects:ro \
  scannerroom:latest
docker image prune -f
echo "Deployment complete!"
