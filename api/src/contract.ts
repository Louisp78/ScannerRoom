/**
 * Shapes of the API's JSON responses, shared with the viewer (`import type`
 * only, so nothing of the API reaches the browser bundle). Keep this file free
 * of imports.
 */

/** A `provider:subject` login, e.g. "orcid:0000-0002-1825-0097". */
export type IdentityKey = `${string}:${string}`

export type Provider = 'orcid' | 'google'

/** GET /api/me: the signed-in user. */
export interface SessionUser {
  id: number
  displayName: string
  orcidId: string | null
  identities: IdentityKey[]
  isAdmin: boolean
}

/** A user as shown to others: transect contributor, admin user list. */
export interface UserSummary {
  id: number
  displayName: string
  orcidId: string | null
}

/** A transect credited to the signed-in user. */
export interface OwnTransect {
  key: string
  showcase: boolean
  /** ISO 8601 timestamp of when the transect was registered. */
  createdAt: string
}

/** GET /api/me/transects: the signed-in user's contributions, newest first. */
export interface OwnTransectsResponse {
  transects: OwnTransect[]
}

/** GET /api/users (admins only) */
export interface UsersResponse {
  users: UserSummary[]
}

/** PUT /api/transects/:key/contributor (admins only); null removes the contributor. */
export interface SetContributorRequest {
  userId: number | null
}

/** GET /api/transects/:key */
export interface TransectDetails {
  key: string
  showcase: boolean
  /** Who added the transect; null until an owner is assigned. */
  contributor: UserSummary | null
  /** The signed-in user may edit it (owner or admin). */
  editable: boolean
}

/** GET /api/auth/providers */
export interface ProvidersResponse {
  providers: Provider[]
}

/** Error body of every non-2xx JSON response. */
export interface ApiError {
  error: string
}
