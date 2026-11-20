# Contributing

How to run ScannerRoom locally, add a transect, and ship changes. For what the
project is, see the [README](README.md).

## Requirements

- Node.js 24 and Docker (local database).
- To reconstruct transects: an Apple Silicon Mac (LingBot-Map runs on MLX),
  Python 3.10 and ffmpeg. The VPS cannot reconstruct; reconstruction always
  happens locally.

## Run the app locally

```bash
npm ci && npm ci --prefix api
docker compose up -d db                  # PostgreSQL on 127.0.0.1:5432
cp api/.env.example api/.env             # then fill in an ORCID sandbox or Google client
npm run dev --prefix api                 # API on :3002
npm run dev                              # app on http://localhost:5173 (proxies /api)
```

The atlas and the viewer require signing in, so `api/.env` needs at least one
OAuth client (see the comments in `api/.env.example`).

Transect data is **not in the repository**: the viewer loads it from
`public/transects/<key>/`, which you fill by reconstructing a transect (below)
or, with VPS access, by copying a published one:

```bash
rsync -az louisplace-app:scannerroom/transects/<key>/ public/transects/<key>/
```

The local dev server serves these files without any access check. To also see
the contributor badge, register the transect in the local database:

```bash
cd api && node --env-file=.env scripts/register-transect.ts <key> [--owner orcid:<iD>]
```

## Checks

```bash
npm run check          # oxlint, eslint, prettier
npm run type-check     # app and API
npm test --prefix api  # API tests, against the local database
```

CI runs the same checks on every pull request.

## Add a transect

### 1. Reconstruct it locally

Either from the interface, for your own video:

```bash
npm run dev   # then http://localhost:5173/ingest ("Add a transect" on the map)
```

The form takes the video, a name, a key (folder name), the site position and
the excerpt to reconstruct. It runs the pipeline steps on the dev server and
adds the site to the site catalog. One job at a time; the page only exists on the
dev server.

Or from the scripts, for the NOAA catalog:

```bash
cd playground/scripts
./00-setup-lingbot.sh            # once
./build-catalog.sh [key ...]     # fetch, extract, reconstruct, export; default: whole catalog
```

Count about 45 min per 12 min transect on an M3 Pro, strictly one at a time.
Each step can also be run on its own; see the
[pipeline documentation](playground/README.md) for the steps and their settings.

Both paths write the transect's data folder and its site catalog entry.

### 2. Publish it

```bash
deploy/publish-transect.sh <key>...
```

It uploads the folder to `~/scannerroom/transects/<key>/` on the VPS (only the
changed files, so re-publishing after a re-export is cheap) and registers the
transect in the database. Then commit the site catalog entry and open a pull request:
the point appears on the map once it is deployed. Always publish the data
before the `sites.json` entry that points to it.

The VPS is reached through the ssh host `louisplace-app`; set `SCANNERROOM_SSH`
to use another one.

### 3. Set its access and contributor (optional)

A new transect is private (signed-in users only) and has no contributor. On
the VPS:

```bash
docker exec scannerroom-api node scripts/register-transect.ts <key> --showcase   # readable signed out
docker exec scannerroom-api node scripts/register-transect.ts <key> --owner orcid:<iD>
```

The owner must have signed in once. Admins can also reassign a contributor from
the viewer.

## Pipeline rules

Changes to the reconstruction or the export must work for every transect:

- no per-transect parameters, thresholds or tweaks: derive values from the data
  itself (relative to the median depth, in seconds of video...);
- data processing belongs in the pipeline's web export; the
  viewer only renders;
- validate a change on at least two transects and check it does not regress the
  others.

## Conventions

- Documentation, in Markdown files and in code, is written in English.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
  and name the user story they belong to, as listed in the
  [specification](docs/specs.md):
  `feat(viewer): stream full-detail tiles near the camera (US-3.2 Adaptive level of detail)`.
- Work on a branch and open a pull request to `main`.

## Deployment

Merging to `main` deploys: CI runs the checks, uploads the source to the VPS and
runs the VPS deploy script, which rebuilds the site and API
containers. The database and the transect data
persist across deploys; the data is mounted read-only into the site container,
whose nginx only serves it to signed-in users (or for showcase transects).
