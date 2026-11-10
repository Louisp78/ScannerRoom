# US-4.1 / US-4.2 — Contributor accounts and restricted access

> **US-4.1** — As a contributor, I want to sign in, so that only I (or an admin) can add and edit the biome areas of the transects I added.
>
> **US-4.2** — As the project owner, I want the atlas, the transect viewer and the access request page to be reserved to signed-in users, so that the data is shared with known people only.

Status: **plan**, nothing implemented yet. This branch is merged before `feat/us-2.5-biome-areas`, which is then rebased onto it (see [Impact on US-2.5](#impact-on-us-25-biome-areas)).

## Context

The site is a static bundle (nginx container on the VPS, rebuilt on every push to `main`). Transects are reconstructed locally (LingBot-Map on Apple Silicon, see US-3.3) and committed to the repo. That model cannot express:

1. **identity**: who is the visitor;
2. **ownership**: who added a transect, and therefore who may edit its areas;
3. **persistent writes**: edits made in production cannot live in git or in a container that is rebuilt on every deploy;
4. **access control**: every file under `public/` is downloadable by anyone today.

## Decisions

| Topic | Decision | Why |
|---|---|---|
| Sign-in providers | **ORCID** and **Google** | Contributors are scientists: an ORCID iD is a stable, public researcher identifier usable for attribution. Google covers everyone else. |
| Protocol | OpenID Connect, Authorization Code flow handled by the API (confidential client) | Tokens never reach the browser; one generic OIDC client configured per provider. |
| Session | Server-side session row + `httpOnly`, `Secure`, `SameSite=Lax` cookie | No token in JavaScript or `localStorage`; logout and expiry are enforced server side. |
| Database | **PostgreSQL** with **PostGIS** | Concurrent writers (API, ingest registration, migrations), JSONB for area data, PostGIS for upcoming spatial queries (US-1.4 loading by area). |
| Hosting | API and database on the **same VPS** as the site, for convenience | Single machine for now; the database is never exposed outside the internal docker network. |
| Roles | `contributor` (default) and **`admin`** | Admin can edit any transect and maintain shared data. Admins are listed in the API environment as `provider:subject` entries. |
| Custom biome types | **Removed**, not planned | They would be visible to everyone. Only the IUCN M1 catalogue is kept. |
| Access | Atlas, viewer and request-access page require a session; the landing page stays public | See [Access control](#access-control-us-42). |

## Architecture

```
Browser ──► Cloudflare ──► VPS nginx (native)
                             ├─ /             → scannerroom      static SPA (unchanged image)
                             ├─ /api/*        → scannerroom-api  127.0.0.1:3002
                             └─ /transects/*  → auth_request /api/auth/check, then static files
                           docker network "scannerroom" (internal)
                             ├─ scannerroom-api  ──►  scannerroom-db
                             └─ scannerroom-db   postgis/postgis, volume scannerroom-pgdata,
                                                 no published port
```

- The API is served **same origin** under `/api`: cookies work without CORS.
- The API connects with a dedicated, non-superuser database role.
- Schema migrations are versioned SQL files applied when the API starts, so the CI deploy stays "build image, run container".
- Nightly `pg_dump`, copied off the VPS.
- Local development: `docker compose up db`, the API runs locally, Vite proxies `/api` to it.

## Data model

```
users            (id, display_name, orcid_id NULL, role 'contributor'|'admin', created_at)
user_identities  (provider 'orcid'|'google', subject, user_id)   unique (provider, subject)
sessions         (id, user_id, expires_at, created_at)
transects        (key, owner_id, showcase boolean, created_at)
areas            (transect_key, data jsonb, version int, updated_at, updated_by)
```

- A transect belongs to a **user**, not to a login: the same person may sign in with ORCID or Google.
- **No automatic account linking by email** (the classic account-takeover path, and ORCID rarely shares the email anyway). Linking a second provider only happens explicitly, while signed in.
- `orcid_id` is set once ORCID is linked and shown as the transect author.

## API

| Endpoint | Access | Purpose |
|---|---|---|
| `GET /api/auth/:provider` → `GET /api/auth/:provider/callback` | public | OIDC flow (state + nonce checked) |
| `POST /api/auth/logout` | session | End the session |
| `POST /api/auth/link/:provider` | session | Link another provider to the current user |
| `GET /api/auth/check` | internal (nginx `auth_request`) | 204 if the session is valid, 401 otherwise |
| `GET /api/me` | session | Current user, role, owned transect keys |
| `GET /api/sites` | session | Site list for the atlas (replaces the bundled `sites.json`) |
| `GET /api/transects/:key/areas` | session (public for a showcase transect) | Read areas |
| `PUT /api/transects/:key/areas` | session + **owner or admin** | Replace areas, `If-Match: <version>` |
| `POST /api/transects` | session or ingest API token | Register a transect and its owner (called by the local ingest) |

Security on every write:

- ownership checked server side, never trusted from the client;
- CSRF: `SameSite=Lax` cookie, `Origin` header check, and a required custom header (`X-Requested-With`);
- request body size limit and per-user rate limiting;
- payload validation reused from `vite-plugins/areas.ts`, moved to a module shared by the API and the viewer;
- optimistic concurrency (`If-Match` / version) so two tabs never silently overwrite each other.

## Access control (US-4.2)

| Route / resource | Access |
|---|---|
| `/` landing page | public |
| `/sign-in` | public |
| `/explore` atlas | signed in |
| `/transects/:key` viewer | signed in, except the showcase transect embedded on the landing page |
| `/request-access` | signed in; the form is prefilled from the profile (name, Google email, ORCID iD) |
| `/transects/<key>/*` data files (`cloud.ply`, `path.json`, video) | signed in, enforced by nginx `auth_request`; showcase transects stay public |
| `/api/*` reads | signed in, except auth endpoints and showcase areas |

- **Enforced by the server, not only by the router.** A Vue Router guard (`beforeEach`, `GET /api/me` cached once) redirects to `/sign-in?redirect=…` for a clean UX, but the real protection is nginx `auth_request` on the data files and session checks in the API. The SPA HTML and JS bundle stay public; they hold no data.
- **Showcase transects** (`transects.showcase = true`) keep the landing page working: its embedded viewer loads the featured transect without a session. nginx gets the public keys from a small generated include file, or the API answers `auth/check` with 204 for showcase paths.
- The site list moves from the bundled `src/sites.json` to `GET /api/sites`, otherwise the restricted atlas would still ship every site in the public bundle.

## Ownership of transects

Reconstruction stays local (it needs Apple Silicon). At the end of the ingest pipeline (`register` step in `vite-plugins/ingest.ts`), the transect is registered with `POST /api/transects`, using a personal API token created from the user's account, and owned by that user. The two existing transects are assigned to the admin in the first migration; `site3-transect2-south-return` is flagged `showcase`.

## Impact on US-2.5 biome areas

The storage seam of `feat/us-2.5-biome-areas` is isolated in `src/biomes.ts` (`loadAreas`, `saveAreas`). After rebasing onto this branch:

- `loadAreas` / `saveAreas` call `/api/transects/:key/areas`;
- `canEdit` in `TransectViewer.vue` becomes "signed in and (owner or admin)" instead of `import.meta.env.DEV`;
- `vite-plugins/areas.ts` is deleted; existing `areas.json` files are imported once by a migration;
- the painter, the editor and the IUCN catalogue are unchanged.

## Deployment

- `.github/workflows/build_and_deploy.yml` builds a second image (`scannerroom-api`) and runs it on the internal network next to `scannerroom-db` (volume `scannerroom-pgdata`).
- New GitHub secrets: `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET`, `DATABASE_PASSWORD`, `ADMIN_IDENTITIES`.
- VPS nginx (native) gains `location /api/` and an `auth_request` on `/transects/` for `scannerroom.louisplace.com`.
- Nightly `pg_dump` cron with off-VPS copy.

### Provider setup

- **ORCID**: register a Public API client (free, no Member API needed), scope `openid`; the ID token subject is the ORCID iD. Production redirect URIs must be HTTPS and registered in advance: `https://scannerroom.louisplace.com/api/auth/orcid/callback`. Development uses `sandbox.orcid.org`, which has its own client ID and test accounts. To verify while building: PKCE support (not required, the client secret is kept server side), the discovery document URL, and whether the sandbox accepts a `localhost` redirect. Do not rely on getting an email from ORCID.
- **Google**: OAuth client of type "Web application", scopes `openid email profile`, `http://localhost` redirect allowed for development. Before launch, switch the consent screen to "In production" (in "Testing" only listed accounts can sign in); a logo on the consent screen requires brand verification.

## Out of scope

- Collaborators or shared editing of a transect.
- Moderation workflow and history of area changes.
- Online upload and reconstruction (needs a GPU server).
- Custom biome types.

## Open questions

- **Landing page site list**: the landing page currently lists every site (name, position) from the bundle. Keep that public as a teaser, or show only the count and the showcase once the list moves behind the API?
- **Request access handling**: keep the current `mailto:` handoff (prefilled from the profile), or store requests in the database and notify the admin?
