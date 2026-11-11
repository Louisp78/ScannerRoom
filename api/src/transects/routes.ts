import { Router, type Request } from 'express'
import { z } from 'zod'
import type { TransectDetails } from '../contract.ts'
import { canEdit, HttpError, requireAdmin } from '../auth/guards.ts'
import type { UserStore } from '../auth/users.ts'
import type { TransectRecord, TransectStore } from './store.ts'

const SetContributorBody = z.object({ userId: z.number().int().positive().nullable() })

function details(transect: TransectRecord, user: Request['user']): TransectDetails {
  return {
    key: transect.key,
    showcase: transect.showcase,
    contributor: transect.contributor,
    editable: canEdit(user, transect.ownerId),
  }
}

/** Transect details and contributor changes, under /api/transects. */
export function transectsRouter(transects: TransectStore, users: UserStore): Router {
  const router = Router()

  router.get('/:key', async (req, res) => {
    const transect = await transects.find(req.params.key)
    // Same answer for "missing" and "private" to anonymous visitors: no probing.
    if (!req.user && !transect?.showcase) throw new HttpError(401, 'Sign in required.')
    if (!transect) throw new HttpError(404, 'Unknown transect.')
    res.json(details(transect, req.user))
  })

  /** Admins reassign a transect to another contributor, or leave it without one. */
  router.put('/:key/contributor', requireAdmin, async (req, res) => {
    // Typed loosely by Express once a middleware precedes the handler.
    const key = String(req.params.key)
    const body = SetContributorBody.safeParse(req.body)
    if (!body.success) throw new HttpError(400, 'Expected { userId: number | null }.')
    const { userId } = body.data
    if (userId !== null && !(await users.load(userId))) throw new HttpError(400, 'Unknown user.')
    if (!(await transects.setOwner(key, userId))) throw new HttpError(404, 'Unknown transect.')
    res.json(details((await transects.find(key))!, req.user))
  })

  return router
}
