# US-4.1 / US-4.2 — Contributor accounts and restricted access

> **US-4.1** — As a contributor, I want to sign in, so that only I (or an admin) can add and edit the biome areas of the transects I added, and so that my name is shown on them.
>
> **US-4.2** — As the project owner, I want the atlas and the transect viewer to be reserved to signed-in users, so that the data is shared with known people only.

Status: **in progress**, see [Implementation status](#implementation-status). This branch is merged before `feat/us-2.5-biome-areas`, which is then rebased onto it (see [Impact on US-2.5](#impact-on-us-25-biome-areas)).

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
| Auth library | **Passport.js** with the **`openid-client` Passport strategy** | Passport is the standard Express auth middleware (largest community); `openid-client` implements the OIDC protocol for both providers, so no protocol code is written by hand. |
| Session | `express-session` with a Postgres store (`connect-pg-simple`), `httpOnly`, `Secure`, `SameSite=Lax` cookie | No token in JavaScript or `localStorage`; logout and expiry are enforced server side; session table, expiry and pruning handled by the store. |
| Database | **PostgreSQL** (official `postgres:17-alpine` image), **PostGIS** added when spatial queries arrive | Concurrent writers (API, ingest registration, migrations), JSONB for area data. PostGIS is for the spatial queries of US-1.4; nothing needs it yet, and the `postgis/postgis` image has no arm64 build for local development. Adding it later means switching to a Postgres 17 image that ships PostGIS, on the same volume. |
| Hosting | API and database on the **same VPS** as the site, for convenience | Single machine for now; the database is never exposed outside the internal docker network. |
| Roles | `contributor` (default) and **`admin`** | Admin can edit any transect and maintain shared data. Admins are listed in the API environment (`ADMIN_IDENTITIES`) as `provider:subject` entries; the role is derived on each request, not stored. |
| Custom biome types | **Removed**, not planned | They would be visible to everyone. Only the IUCN M1 catalogue is kept. |
| Access | Atlas and viewer require a session; the landing page (with its site teaser) and the request-access page stay public | See [Access control](#access-control-us-42). |
| Attribution | The contributor's name is shown in the viewer, in the badge holding the coordinates | See [Contributor in the viewer](#contributor-in-the-viewer). |
| API stack | **Node 24 + TypeScript + Express 5** | Largest community and integration ecosystem; see [Tech stack](#tech-stack). |

## Architecture

```
Browser ──► Cloudflare ──► VPS nginx (native, unchanged) ──► 127.0.0.1:3001
                           docker network "scannerroom" (internal)
                             ├─ scannerroom       site nginx (nginx.conf in the repo)
                             │    ├─ /                       static SPA
                             │    ├─ /api/*                  → scannerroom-api:3002
                             │    └─ /transects/<key>/*      auth_request /api/auth/check, then the file
                             ├─ scannerroom-api   Express, not published
                             └─ scannerroom-db    postgres:17-alpine, volume scannerroom-pgdata,
                                                  not published
```

- All routing lives in the repo's `nginx.conf` (the site container); the VPS nginx keeps proxying everything to `127.0.0.1:3001` and needs no change.
- The API is served **same origin** under `/api`: cookies work without CORS.
- The API connects with a dedicated, non-superuser database role.
- Schema migrations are versioned SQL files applied when the API starts, so the CI deploy stays "build image, run container".
- Nightly `pg_dump`, copied off the VPS.
- Local development: `docker compose up db`, the API runs locally, Vite proxies `/api` to it.

## Tech stack

| Need | Choice | Notes |
|---|---|---|
| Runtime | Node 24, TypeScript | Same toolchain as the front end (npm, ESLint, oxlint, Prettier); one `node:24-alpine` image. |
| HTTP framework | **Express 5** | Chosen for its community and ecosystem. Version 5 forwards errors thrown in `async` handlers to the error middleware. |
| Express middleware | `helmet`, `express-rate-limit`, `express.json({ limit })` | `cookie-parser` is not needed: `express-session` reads its own cookie. CSRF has no maintained Express package (`csurf` is deprecated): a small in-house middleware checks the `Origin` header and the required `X-Requested-With` header on writes. |
| Sign-in | `passport` + `openid-client/passport` strategy | `openid-client` handles discovery, PKCE, state, nonce, code exchange and ID token validation (signature, issuer, audience, expiry). One strategy instance per provider (`orcid`, `google`). Provider-specific packages (`passport-orcid`, `passport-google-oauth20`) are not used: the first is barely maintained, the second is plain OAuth2 without OIDC checks. |
| Sessions | `express-session` + `connect-pg-simple` | Sessions stored in Postgres; cookie `httpOnly`, `Secure`, `SameSite=Lax`, session id regenerated on sign-in. Sessions last 30 days from sign-in and are not extended on activity: nginx asks `/api/auth/check` for every data file (video chunks included), and refreshing the session each time would be a database write per request. |
| Database access | Drizzle ORM + `pg` (node-postgres) driver | Typed schema in TypeScript, SQL migrations generated by `drizzle-kit`, raw SQL for PostGIS. `pg` is also what `connect-pg-simple` uses: one driver and one connection pool for the whole API. |
| Validation | Zod | One `Area` schema shared by the API and the viewer, replacing the hand-written checks of `vite-plugins/areas.ts`. |
| Tests | Vitest + Supertest | Supertest drives the Express app in-process. |

Rejected: **NestJS** (modules, dependency injection and decorators are overhead for about ten endpoints, and `class-validator` DTOs do not share with the Vue front end), **Hono** and **Fastify** (smaller community than Express), **Better Auth / Auth.js** (impose their own schema and session model, harder to fit ORCID linking and nginx `auth_request`), **Supabase / PocketBase** (heavy self-hosting, or SQLite), **Prisma** (the best-known ORM, but its schema lives in a separate `.prisma` language and PostGIS columns are unsupported, so every spatial query would be raw SQL; Drizzle is TypeScript-first, supports PostGIS `geometry` columns, and now has the larger npm usage).

Layout:

```
api/
  src/
    index.ts          start-up: config, migrations, providers, listen
    app.ts            Express app: middleware, sessions, routes, /api/auth/check
    config.ts         environment, validated with Zod
    contract.ts       response types shared with the viewer (no imports)
    auth/             Passport (own instance) + openid-client strategies, users and
                      identities, guards, CSRF check, sign-in routes
    db/               Drizzle schema, pool, migrations runner
    routes/           transects
  scripts/            maintenance (register-transect.ts)
  test/               Vitest + Supertest, against a real Postgres
  drizzle/            generated SQL migrations
  db-init/            first-start database setup (API role)
  Dockerfile
docker-compose.yml    local Postgres
```

`api/src/contract.ts` holds the API's response types; the viewer imports them as types only (`src/api.ts`). Once US-2.5 is rebased, the `Area` Zod schema joins it and is shared the same way.

### Auth: what the libraries do, what we write

Handled by libraries: the whole OIDC protocol (`openid-client`), wiring it into Express routes and `req.user` (Passport), session cookies and storage (`express-session`, `connect-pg-simple`).

Written in the API (application rules, about a hundred lines):

- **verify callback**: look up `(provider, subject)` in `user_identities`; create the user on first sign-in; never link to an existing user by email;
- **explicit linking**: `GET /api/auth/:provider/link` (signed in) starts a provider login whose identity is attached to the current user;
- **`serializeUser` / `deserializeUser`**: the session stores only the user id;
- **guards**: `requireAuth`, `requireOwner(transectKey)`, `requireAdmin` (admins from `ADMIN_IDENTITIES`);
- **`GET /api/auth/check`** for nginx `auth_request`;
- **CSRF check** on writes (`Origin` header + required `X-Requested-With`).

### TypeScript everywhere it fits

Every new piece of code is TypeScript, with the same strictness as the front end (`strict`, `noUncheckedIndexedAccess`):

- **API**: routes, middleware, auth, error handling.
- **Database**: Drizzle schema in `api/src/db/schema.ts`; queries are typed from it, so a column change breaks the build instead of production.
- **One-off and maintenance scripts**: the first migration importing existing `areas.json` files, assigning the existing transects to the admin, creating ingest API tokens. They run with Node 24 directly (`node script.ts`, native type stripping), no extra runner.
- **Shared contract**: API request and response types are inferred from the Zod schemas (`z.infer`), and the viewer imports them, so both sides change together.
- **Type-checking in CI**: `api/tsconfig.json` is added to the root project references, so the existing `npm run type-check` (`vue-tsc --build`) checks the API too.

Kept as they are, because TypeScript is not the right tool there:

- **Reconstruction and export** (`playground/scripts/*.py`): Python, bound to LingBot-Map, MLX and NumPy.
- **Pipeline wrappers** (`playground/scripts/*.sh`): thin shell glue around those Python tools.
- **Infrastructure files**: `Dockerfile`, `docker-compose.yml`, nginx config, GitHub workflow (each has its own format).
- **Generated SQL migrations** (`api/drizzle/*.sql`): produced by `drizzle-kit` from the TypeScript schema, not written by hand.

## Data model

```
users            (id, display_name, orcid_id NULL unique, created_at)
user_identities  (provider 'orcid'|'google', subject, user_id)   unique (provider, subject)
session          (sid, sess jsonb, expire)   created and pruned by connect-pg-simple
transects        (key, owner_id, showcase boolean, created_at)
areas            (transect_key, data jsonb, version int, updated_at, updated_by)   added with US-2.5
```

- A transect belongs to a **user**, not to a login: the same person may sign in with ORCID or Google.
- **No automatic account linking by email** (the classic account-takeover path, and ORCID rarely shares the email anyway). Linking a second provider only happens explicitly, while signed in.
- `orcid_id` is set once ORCID is linked and shown as the transect author.

## API

| Endpoint | Access | Purpose |
|---|---|---|
| `GET /api/auth/providers` | public | Configured providers, for the sign-in page |
| `GET /api/auth/:provider?returnTo=…` → `GET /api/auth/:provider/callback` | public | OIDC flow (PKCE always, plus `state` for ORCID, which does not advertise PKCE) |
| `GET /api/auth/:provider/link?returnTo=…` | session | Link another provider to the current user |
| `POST /api/auth/logout` | session | End the session |
| `GET /api/auth/check` | internal (nginx `auth_request`) | 204 if signed in or the URI is a showcase transect's file, 401 otherwise |
| `GET /api/me` | session | Current user, identities, admin flag |
| `GET /api/transects/:key` | session (public for a showcase transect) | Transect details for the viewer: contributor, and whether the user may edit it |
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
| `/request-access` | public, **unchanged in this MR** (see [Out of scope](#out-of-scope)) |
| `/transects/<key>/*` data files (`cloud.ply`, `path.json`, video) | signed in, enforced by nginx `auth_request`; showcase transects stay public |
| `/api/*` reads | signed in, except auth endpoints and showcase areas |

- **Enforced by the server, not only by the router.** A Vue Router guard (`beforeEach`, `GET /api/me` cached once) redirects to `/sign-in?redirect=…` for a clean UX, but the real protection is nginx `auth_request` on the data files and session checks in the API. The SPA HTML and JS bundle stay public; they hold no data.
- **Showcase transects** (`transects.showcase = true`) keep the landing page working: its embedded viewer loads the featured transect without a session. nginx forwards the original URI to `/api/auth/check`, which answers 204 for a showcase transect's files.
- **Never cached by Cloudflare.** Protected files are served with `Cache-Control: private, no-store`: an edge copy (Cloudflare caches `.mp4` by default) would otherwise be served to anyone, bypassing the check.
- **Site summaries stay public as a teaser.** The landing page keeps showing every site's name and position, as it does today: `src/sites.json` stays in the bundle. What is protected is the data itself (point cloud, path, video, areas) and the atlas and viewer pages.

## Contributor in the viewer

The site badge at the top left of the transect viewer (`TransectViewer.vue`, the container holding the site name and its coordinates) gains a third line with the contributor:

```
Old Kona, site 3 — transect 2
19.6450° N, 156.0250° W
by Jane Doe · ORCID 0000-0002-1825-0097
```

- The name is the owner's `display_name`. When the owner linked ORCID, the iD is shown as a link to `https://orcid.org/<iD>`, which makes the attribution verifiable.
- The data comes from `GET /api/transects/:key` (`{ key, contributor: { displayName, orcidId } }`), with the same access as the viewer: signed in, or public for a showcase transect so the landing page embed shows it too.
- The badge is `pointer-events-none` today so it never blocks the 3D view; only the ORCID link gets pointer events back.
- Until the transect is registered with an owner, the line is simply not shown.

## Ownership of transects

Reconstruction stays local (it needs Apple Silicon). At the end of the ingest pipeline (`register` step in `vite-plugins/ingest.ts`), the transect is registered with `POST /api/transects`, using a personal API token created from the user's account, and owned by that user.

Until then, and for the existing transects, `api/scripts/register-transect.ts` registers a transect, flags it showcase or private, and assigns its owner by login (`--owner orcid:<iD>`, once that person has signed in). In production: `docker exec scannerroom-api node scripts/register-transect.ts <key> [--showcase] [--owner provider:subject]`. A transect without owner is editable by admins only.

## Impact on US-2.5 biome areas

The storage seam of `feat/us-2.5-biome-areas` is isolated in `src/biomes.ts` (`loadAreas`, `saveAreas`). After rebasing onto this branch:

- `loadAreas` / `saveAreas` call `/api/transects/:key/areas`;
- `canEdit` in `TransectViewer.vue` becomes "signed in and (owner or admin)" instead of `import.meta.env.DEV`;
- `vite-plugins/areas.ts` is deleted; existing `areas.json` files are imported once by a migration;
- the painter, the editor and the IUCN catalogue are unchanged.

## Deployment

- `.github/workflows/build_and_deploy.yml`:
  - a `test-api` job runs the API tests against a Postgres service, and gates the deploy;
  - the deploy creates the `scannerroom` docker network, starts `scannerroom-db` once (kept across deploys, volume `scannerroom-pgdata`, init script copied to `~/scannerroom/db-init`), writes `~/scannerroom/api.env` (mode 600) from the secrets, then rebuilds and restarts `scannerroom-api` and the site, both on that network.
- New GitHub secrets, **required before merging** (without `SESSION_SECRET` and the database passwords the API cannot start, and then even showcase files are refused): `DB_SUPERUSER_PASSWORD`, `DATABASE_PASSWORD`, `SESSION_SECRET` (`openssl rand -base64 48`), `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_IDENTITIES`.
- After the first deploy: `docker exec scannerroom-api node scripts/register-transect.ts site3-transect2-south-return --showcase`, and register `tab-south`.
- `TRUST_PROXY_HOPS=3` (Cloudflare, VPS nginx, site nginx) only affects the client IP used by the rate limiter; to confirm on the VPS.
- Nightly `pg_dump` cron with off-VPS copy.

### Provider setup

- **ORCID**: register a Public API client (free, no Member API needed), scope `openid`; the ID token subject is the ORCID iD. Production redirect URIs must be HTTPS and registered in advance: `https://scannerroom.louisplace.com/api/auth/orcid/callback`. Development uses `sandbox.orcid.org` (`ORCID_ISSUER`), which has its own client ID and test accounts. Checked: both publish an OpenID discovery document (`/.well-known/openid-configuration`), accept the client secret only in the request body (`client_secret_post`), and do not advertise PKCE (the strategy then adds `state`). Still to check: whether the sandbox accepts a `localhost` redirect. Do not rely on getting an email from ORCID.
- **Google**: OAuth client of type "Web application", scopes `openid email profile`, `http://localhost` redirect allowed for development. Before launch, switch the consent screen to "In production" (in "Testing" only listed accounts can sign in); a logo on the consent screen requires brand verification.

## Out of scope

- **Request access page**: any change to it (session-prefilled form, storing requests in the database instead of the `mailto:` handoff) is a separate MR.
- Collaborators or shared editing of a transect.
- Moderation workflow and history of area changes.
- Online upload and reconstruction (needs a GPU server).
- Custom biome types.

## Implementation status

Done in this branch:

- API (`api/`): config, Drizzle schema and first migration, ORCID and Google sign-in through Passport + `openid-client`, explicit linking, sessions in Postgres, admin from `ADMIN_IDENTITIES`, CSRF check, rate limit on sign-in, `GET /api/me`, `GET /api/transects/:key`, `GET /api/auth/check`, `register-transect.ts` script.
- Tests: 20 Vitest + Supertest tests against a real Postgres (accounts, linking rules, admin, access to transects, nginx check, CSRF, sign-out, open-redirect protection).
- Viewer: sign-in page, router guard on the atlas and the viewer (showcase transects stay open), account menu with ORCID linking and sign-out, contributor line in the viewer badge, Vite proxy to the API.
- Infrastructure: site `nginx.conf` (`/api` proxy, `auth_request` on transect files, no edge caching), API Dockerfile, `docker-compose.yml` for local Postgres, CI test job and deploy of the API and the database.

Still to do:

- Register the ORCID and Google clients and create the GitHub secrets (manual).
- Ingest registration: personal API tokens and `POST /api/transects`, called by the `register` step of the ingest.
- Nightly `pg_dump` with off-VPS copy.
- Areas endpoints and table, with the US-2.5 rebase.

## Open questions

None at this point.
