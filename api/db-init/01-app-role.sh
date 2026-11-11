#!/bin/sh
# Runs once, when the Postgres volume is first initialised (docker-entrypoint-initdb.d).
# The API connects as its own role instead of the superuser: it owns the
# database (so migrations can create tables) but cannot touch anything else.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE scannerroom_api LOGIN PASSWORD '${APP_DB_PASSWORD}';
ALTER DATABASE "${POSTGRES_DB}" OWNER TO scannerroom_api;
SQL

# Local development only: a throwaway database for the API test suite.
if [ "${CREATE_TEST_DATABASE:-}" = "1" ]; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "CREATE DATABASE \"${POSTGRES_DB}_test\" OWNER scannerroom_api;"
fi
