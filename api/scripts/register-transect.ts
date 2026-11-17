/**
 * Registers transects in the database, or updates them.
 *
 *   node --env-file=.env scripts/register-transect.ts <key>... [--showcase | --private] [--owner provider:subject]
 *
 * Without options an already registered transect is left untouched, so the deploy
 * registers every deployed transect folder on each run.
 * --showcase makes its data readable without signing in (landing page embed);
 * --owner gives it to the user holding that login (they must have signed in once).
 */
import { parseArgs } from 'node:util'
import { and, eq, inArray } from 'drizzle-orm'
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
const keyPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
if (
  !positionals.length ||
  !positionals.every((key) => keyPattern.test(key)) ||
  (values.showcase && values.private)
) {
  console.error(
    'Usage: register-transect.ts <key>... [--showcase | --private] [--owner provider:subject]',
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
  const insert = db
    .insert(transects)
    .values(positionals.map((key) => ({ key, ownerId, showcase: showcase ?? false })))
  await (Object.keys(changes).length
    ? insert.onConflictDoUpdate({ target: transects.key, set: changes })
    : insert.onConflictDoNothing())
  console.log(await db.query.transects.findMany({ where: inArray(transects.key, positionals) }))
} finally {
  await pool.end()
}
