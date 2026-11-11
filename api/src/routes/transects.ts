import { eq } from 'drizzle-orm'
import { Router } from 'express'
import type { TransectDetails } from '../contract.ts'
import type { Db } from '../db/client.ts'
import { transects, users } from '../db/schema.ts'
import { canEdit, HttpError } from '../auth/guards.ts'

export function transectsRouter(db: Db) {
  async function find(key: string) {
    const [row] = await db
      .select({
        key: transects.key,
        showcase: transects.showcase,
        ownerId: transects.ownerId,
        displayName: users.displayName,
        orcidId: users.orcidId,
      })
      .from(transects)
      .leftJoin(users, eq(users.id, transects.ownerId))
      .where(eq(transects.key, key))
    return row
  }

  /** Whether a transect's data is readable without a session. */
  async function isShowcase(key: string): Promise<boolean> {
    return (await find(key))?.showcase ?? false
  }

  const router = Router()

  router.get('/:key', async (req, res) => {
    const row = await find(req.params.key)
    // Same answer for "missing" and "private" to anonymous visitors: no probing.
    if (!req.user && !row?.showcase) throw new HttpError(401, 'Sign in required.')
    if (!row) throw new HttpError(404, 'Unknown transect.')
    const details: TransectDetails = {
      key: row.key,
      showcase: row.showcase,
      contributor: row.displayName ? { displayName: row.displayName, orcidId: row.orcidId } : null,
      editable: canEdit(req.user, row.ownerId),
    }
    res.json(details)
  })

  return { router, isShowcase }
}
