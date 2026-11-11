import { eq } from 'drizzle-orm'
import { Router, type Request } from 'express'
import { z } from 'zod'
import type { TransectDetails } from '../contract.ts'
import type { Db } from '../db/client.ts'
import { transects, users } from '../db/schema.ts'
import { canEdit, HttpError, requireAdmin } from '../auth/guards.ts'

const SetContributorBody = z.object({ userId: z.number().int().positive().nullable() })

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

  function details(row: NonNullable<Awaited<ReturnType<typeof find>>>, user: Request['user']) {
    const result: TransectDetails = {
      key: row.key,
      showcase: row.showcase,
      contributor:
        row.ownerId !== null && row.displayName !== null
          ? { id: row.ownerId, displayName: row.displayName, orcidId: row.orcidId }
          : null,
      editable: canEdit(user, row.ownerId),
    }
    return result
  }

  const router = Router()

  router.get('/:key', async (req, res) => {
    const row = await find(req.params.key)
    // Same answer for "missing" and "private" to anonymous visitors: no probing.
    if (!req.user && !row?.showcase) throw new HttpError(401, 'Sign in required.')
    if (!row) throw new HttpError(404, 'Unknown transect.')
    res.json(details(row, req.user))
  })

  /** Admins reassign a transect to another contributor, or leave it without one. */
  router.put('/:key/contributor', requireAdmin, async (req, res) => {
    // Typed loosely by Express once a middleware precedes the handler.
    const key = String(req.params.key)
    const body = SetContributorBody.safeParse(req.body)
    if (!body.success) throw new HttpError(400, 'Expected { userId: number | null }.')
    const { userId } = body.data
    if (userId !== null) {
      const [user] = await db.select({ id: users.id }).from(users).where(eq(users.id, userId))
      if (!user) throw new HttpError(400, 'Unknown user.')
    }
    const updated = await db
      .update(transects)
      .set({ ownerId: userId })
      .where(eq(transects.key, key))
      .returning({ key: transects.key })
    if (!updated.length) throw new HttpError(404, 'Unknown transect.')
    res.json(details((await find(key))!, req.user))
  })

  return { router, isShowcase }
}
