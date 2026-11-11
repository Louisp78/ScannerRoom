import { and, eq } from 'drizzle-orm'
import type { IdentityKey, Provider, SessionUser, UserSummary } from '../contract.ts'
import type { Db } from '../db/client.ts'
import { userIdentities, users } from '../db/schema.ts'

export type { Provider, SessionUser }

/** ID token claims used to build a profile; every one but `sub` may be missing. */
export interface IdentityClaims {
  sub: string
  name?: unknown
  given_name?: unknown
  family_name?: unknown
}

export class IdentityConflictError extends Error {
  constructor() {
    super('This login is already linked to another ScannerRoom account.')
  }
}

const text = (v: unknown) => (typeof v === 'string' && v.trim() ? v.trim() : undefined)

/** Best display name the provider shares; ORCID records may keep names private. */
function displayNameOf(provider: Provider, claims: IdentityClaims): string {
  const full = [text(claims.given_name), text(claims.family_name)].filter(Boolean).join(' ')
  return (
    text(claims.name) ?? (full || (provider === 'orcid' ? `ORCID ${claims.sub}` : 'Contributor'))
  )
}

export function createUserStore(db: Db, adminIdentities: ReadonlySet<IdentityKey>) {
  async function load(userId: number): Promise<SessionUser | undefined> {
    const user = await db.query.users.findFirst({ where: eq(users.id, userId) })
    if (!user) return undefined
    const rows = await db
      .select({ provider: userIdentities.provider, subject: userIdentities.subject })
      .from(userIdentities)
      .where(eq(userIdentities.userId, userId))
    const identities = rows.map((r): IdentityKey => `${r.provider}:${r.subject}`)
    return {
      id: user.id,
      displayName: user.displayName,
      orcidId: user.orcidId,
      identities,
      // Derived from the environment on every load, so changing ADMIN_IDENTITIES
      // takes effect without touching the database.
      isAdmin: identities.some((i) => adminIdentities.has(i)),
    }
  }

  /**
   * Resolves a successful provider login to a user.
   *
   * - Known identity: that identity's user; refused when another user is
   *   trying to link it to their own account.
   * - Unknown identity while linking: attached to the signed-in user.
   * - Unknown identity otherwise: a new user. Never matched to an existing
   *   user by email, which would let whoever controls an email address at one
   *   provider take over an account.
   */
  async function signIn(
    provider: Provider,
    claims: IdentityClaims,
    linkToUserId?: number,
  ): Promise<SessionUser> {
    const userId = await db.transaction(async (tx) => {
      const existing = await tx.query.userIdentities.findFirst({
        where: and(eq(userIdentities.provider, provider), eq(userIdentities.subject, claims.sub)),
      })
      if (existing) {
        if (linkToUserId !== undefined && existing.userId !== linkToUserId)
          throw new IdentityConflictError()
        return existing.userId
      }

      let id = linkToUserId
      if (id === undefined) {
        const [created] = await tx
          .insert(users)
          .values({ displayName: displayNameOf(provider, claims) })
          .returning({ id: users.id })
        id = created!.id
      }
      await tx.insert(userIdentities).values({ provider, subject: claims.sub, userId: id })
      if (provider === 'orcid') {
        // The ORCID iD is the public attribution of the user's transects.
        await tx.update(users).set({ orcidId: claims.sub }).where(eq(users.id, id))
      }
      return id
    })
    return (await load(userId))!
  }

  /** Everyone who signed in at least once, by name. */
  function list(): Promise<UserSummary[]> {
    return db
      .select({ id: users.id, displayName: users.displayName, orcidId: users.orcidId })
      .from(users)
      .orderBy(users.displayName, users.id)
  }

  return { load, signIn, list }
}

export type UserStore = ReturnType<typeof createUserStore>
