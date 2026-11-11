import { desc, eq } from 'drizzle-orm'
import type { OwnTransect, UserSummary } from '../contract.ts'
import type { Db } from '../db/client.ts'
import { transects, users } from '../db/schema.ts'

/** A registered transect with its contributor, if any. */
export interface TransectRecord {
  key: string
  showcase: boolean
  ownerId: number | null
  contributor: UserSummary | null
}

/** Database access for transects; the HTTP side lives in ./routes.ts. */
export function createTransectStore(db: Db) {
  async function find(key: string): Promise<TransectRecord | undefined> {
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
    if (!row) return undefined
    const { displayName, orcidId, ...transect } = row
    return {
      ...transect,
      contributor:
        transect.ownerId !== null && displayName !== null
          ? { id: transect.ownerId, displayName, orcidId }
          : null,
    }
  }

  /** Whether a transect's data is readable without a session. */
  async function isShowcase(key: string): Promise<boolean> {
    const [row] = await db
      .select({ showcase: transects.showcase })
      .from(transects)
      .where(eq(transects.key, key))
    return row?.showcase ?? false
  }

  /** The transects credited to a user, newest first. */
  async function listOwnedBy(userId: number): Promise<OwnTransect[]> {
    const rows = await db
      .select({ key: transects.key, showcase: transects.showcase, createdAt: transects.createdAt })
      .from(transects)
      .where(eq(transects.ownerId, userId))
      .orderBy(desc(transects.createdAt), transects.key)
    return rows.map((r) => ({ ...r, createdAt: r.createdAt.toISOString() }))
  }

  /** Gives the transect to a user, or to nobody (null); false when the transect is unknown. */
  async function setOwner(key: string, userId: number | null): Promise<boolean> {
    const updated = await db
      .update(transects)
      .set({ ownerId: userId })
      .where(eq(transects.key, key))
      .returning({ key: transects.key })
    return updated.length > 0
  }

  return { find, isShowcase, listOwnedBy, setOwner }
}

export type TransectStore = ReturnType<typeof createTransectStore>
