import { sql } from 'drizzle-orm'
import request from 'supertest'
import { createApp } from '../src/app.ts'
import { createUserStore } from '../src/auth/users.ts'
import { loadConfig, type IdentityKey } from '../src/config.ts'
import { connect, runMigrations } from '../src/db/client.ts'
import { createTransectStore } from '../src/transects/store.ts'

export const PUBLIC_URL = 'http://localhost:5173'

/** App wired to the test database, with no provider and a test-only sign-in route. */
export async function setUp(adminIdentities: IdentityKey[] = []) {
  const config = loadConfig({
    DATABASE_URL: process.env.DATABASE_URL,
    SESSION_SECRET: 'x'.repeat(32),
    PUBLIC_URL,
    ADMIN_IDENTITIES: adminIdentities.join(','),
  })
  const { db, pool } = connect(config.databaseUrl)
  await runMigrations(db)
  await db.execute(sql`TRUNCATE users, user_identities, transects RESTART IDENTITY CASCADE`)
  const users = createUserStore(db, config.adminIdentities)

  const app = createApp({
    config,
    pool,
    users,
    transects: createTransectStore(db),
    strategies: [],
    // Stands in for the provider round trip, which needs a real ORCID or Google.
    beforeRoutes: (app) =>
      app.post('/test/login/:id', async (req, res, next) => {
        const user = await users.load(Number(req.params.id))
        req.login(user!, (err) => (err ? next(err) : res.status(204).end()))
      }),
  })

  /** A cookie-keeping client signed in as the given user. */
  async function agentFor(userId: number) {
    const agent = request.agent(app)
    await agent.post(`/test/login/${userId}`).expect(204)
    return agent
  }

  return { app, db, pool, users, agentFor }
}

/** Headers every write from the site carries (see csrfCheck). */
export const SAME_SITE = { Origin: PUBLIC_URL, 'X-Requested-With': 'ScannerRoom' }
