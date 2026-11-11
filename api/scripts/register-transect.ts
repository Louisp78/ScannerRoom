/**
 * Registers a transect in the database, or updates it.
 *
 *   node --env-file=.env scripts/register-transect.ts <key> [--showcase | --private] [--owner provider:subject]
 *
 * --showcase makes its data readable without signing in (landing page embed);
 * --owner gives it to the user holding that login (they must have signed in once).
 */
import { parseArgs } from 'node:util'
import { and, eq } from 'drizzle-orm'
import { connect, runMigrations } from '../src/db/client.ts'
import { transects, userIdentities } from '../src/db/schema.ts'

const { positionals, values } = parseArgs({
  allowPositionals: true,
  options: {
    showcase: { type: 'boolean' },
    private: { type: 'boolean' },
    owner: { type: 'string' },
  },
})
const key = positionals[0]
if (!key || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(key) || (values.showcase && values.private)) {
  console.error(
    'Usage: register-transect.ts <key> [--showcase | --private] [--owner provider:subject]',
  )
  process.exit(1)
}

const { db, pool } = connect(process.env.DATABASE_URL ?? '')
try {
  await runMigrations(db)
  let ownerId: number | undefined
  if (values.owner) {
    const [provider, subject] = values.owner.split(/:(.*)/s)
    if (provider !== 'orcid' && provider !== 'google')
      throw new Error('Owner provider must be orcid or google.')
    const identity = await db.query.userIdentities.findFirst({
      where: and(eq(userIdentities.provider, provider), eq(userIdentities.subject, subject ?? '')),
    })
    if (!identity) throw new Error(`No user has signed in with ${values.owner} yet.`)
    ownerId = identity.userId
  }
  const showcase = values.showcase ? true : values.private ? false : undefined
  // Only the given options change an existing row.
  const changes = {
    ...(ownerId !== undefined && { ownerId }),
    ...(showcase !== undefined && { showcase }),
  }
  const insert = db.insert(transects).values({ key, ownerId, showcase: showcase ?? false })
  await (Object.keys(changes).length
    ? insert.onConflictDoUpdate({ target: transects.key, set: changes })
    : insert.onConflictDoNothing())
  console.log(await db.query.transects.findFirst({ where: eq(transects.key, key) }))
} finally {
  await pool.end()
}
