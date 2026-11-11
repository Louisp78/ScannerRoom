/**
 * Client of the ScannerRoom API (api/, US-4.1), served on the same origin
 * under /api: the session cookie travels without any token handling here.
 */
import type {
  ApiError,
  Provider,
  ProvidersResponse,
  SessionUser,
  SetContributorRequest,
  TransectDetails,
  UserSummary,
  UsersResponse,
} from '../api/src/contract'

export type { Provider, SessionUser, TransectDetails, UserSummary }

export class ApiRequestError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(`/api${path}`, {
    ...init,
    credentials: 'same-origin',
    // Required on writes by the API's CSRF check; harmless on reads.
    headers: { 'X-Requested-With': 'ScannerRoom', ...init.headers },
  })
  if (!r.ok) {
    const body = (await r.json().catch(() => ({}))) as Partial<ApiError>
    throw new ApiRequestError(r.status, body.error ?? `HTTP ${r.status}`)
  }
  return (r.status === 204 ? undefined : await r.json()) as T
}

/** Resolves to undefined when the request is answered 401 (signed out). */
async function unlessSignedOut<T>(request: Promise<T>): Promise<T | undefined> {
  try {
    return await request
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 401) return undefined
    throw e
  }
}

let me: Promise<SessionUser | undefined> | undefined

/** The signed-in user, fetched once per page load; undefined when signed out. */
export function getMe(): Promise<SessionUser | undefined> {
  me ??= unlessSignedOut(call<SessionUser>('/me')).catch((e) => {
    me = undefined // retry on the next navigation after a network error
    throw e
  })
  return me
}

/** Details of a transect; undefined when the visitor may not see it (signed out, not a showcase). */
export function getTransect(key: string): Promise<TransectDetails | undefined> {
  return unlessSignedOut(call<TransectDetails>(`/transects/${encodeURIComponent(key)}`))
}

/** Every user, for admins choosing a transect's contributor. */
export async function getUsers(): Promise<UserSummary[]> {
  return (await call<UsersResponse>('/users')).users
}

/** Admins only: assign the transect to another user, or to nobody (null). */
export function setContributor(key: string, userId: number | null): Promise<TransectDetails> {
  const body: SetContributorRequest = { userId }
  return call<TransectDetails>(`/transects/${encodeURIComponent(key)}/contributor`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function getProviders(): Promise<Provider[]> {
  return (await call<ProvidersResponse>('/auth/providers')).providers
}

/** Full-page navigation to the provider: the API redirects back to `returnTo` once signed in. */
export function signInUrl(provider: Provider, returnTo: string, link = false): string {
  const path = link ? `/api/auth/${provider}/link` : `/api/auth/${provider}`
  return `${path}?${new URLSearchParams({ returnTo })}`
}

export async function signOut(): Promise<void> {
  await call<void>('/auth/logout', { method: 'POST' })
  me = undefined
}
