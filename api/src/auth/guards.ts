import type { NextFunction, Request, Response } from 'express'

export class HttpError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Rejects anonymous requests. */
export function requireAuth(req: Request, _res: Response, next: NextFunction) {
  next(req.user ? undefined : new HttpError(401, 'Sign in required.'))
}

/** Rejects anyone but admins. */
export function requireAdmin(req: Request, _res: Response, next: NextFunction) {
  if (!req.user) return next(new HttpError(401, 'Sign in required.'))
  next(req.user.isAdmin ? undefined : new HttpError(403, 'Admins only.'))
}

/**
 * Whether the signed-in user may edit a transect: its owner, or an admin. A
 * transect without owner is editable by admins only.
 */
export function canEdit(user: Express.User | undefined, ownerId: number | null): boolean {
  return !!user && (user.isAdmin || (ownerId !== null && ownerId === user.id))
}

/**
 * CSRF protection for state-changing requests. The session cookie is
 * SameSite=Lax already; on top of that, a write must come from the site's own
 * origin and carry a custom header, which a cross-site form cannot set.
 */
export function csrfCheck(publicUrl: URL) {
  return (req: Request, _res: Response, next: NextFunction) => {
    if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) return next()
    const origin = req.get('origin')
    if (origin !== publicUrl.origin || req.get('x-requested-with') !== 'ScannerRoom')
      return next(new HttpError(403, 'Cross-site request refused.'))
    next()
  }
}
