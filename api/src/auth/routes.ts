import { Router, type NextFunction, type Request, type Response } from 'express'
import type { Authenticator } from './passport.ts'
import { requireAuth } from './guards.ts'
import { IdentityConflictError, type Provider, type SessionUser } from './users.ts'

/** Only same-site paths, so the sign-in flow cannot be turned into an open redirect. */
export function safeReturnTo(value: unknown): string {
  return typeof value === 'string' && /^\/(?![/\\])/.test(value) ? value : '/explore'
}

/** Sign-in, account linking and sign-out, under /api/auth. */
export function authRouter(auth: Authenticator, enabled: readonly Provider[]): Router {
  const router = Router()
  const isEnabled = (name: unknown): name is Provider => enabled.includes(name as Provider)

  router.get('/providers', (_req, res) => {
    res.json({ providers: enabled })
  })

  router.get('/:provider', (req, res, next) => {
    const { provider } = req.params
    if (!isEnabled(provider)) return res.status(404).json({ error: 'Unknown provider.' })
    req.session.returnTo = safeReturnTo(req.query.returnTo)
    delete req.session.linkTo
    auth.authenticate(provider)(req, res, next)
  })

  // Linking: the provider login of the callback is attached to the signed-in user.
  router.get('/:provider/link', requireAuth, (req, res, next) => {
    const { provider } = req.params
    if (!isEnabled(provider)) return res.status(404).json({ error: 'Unknown provider.' })
    req.session.returnTo = safeReturnTo(req.query.returnTo)
    req.session.linkTo = req.user!.id
    auth.authenticate(provider)(req, res, next)
  })

  router.get('/:provider/callback', (req: Request, res: Response, next: NextFunction) => {
    const { provider } = req.params
    if (!isEnabled(provider)) return res.status(404).json({ error: 'Unknown provider.' })
    // Read before req.login(), which regenerates the session (fixation protection).
    const returnTo = safeReturnTo(req.session.returnTo)
    const failed = (reason: string) => res.redirect(`/sign-in?error=${reason}`)

    auth.authenticate(provider, (err: unknown, user: SessionUser | false) => {
      if (err instanceof IdentityConflictError) return failed('linked-elsewhere')
      if (err) return next(err)
      if (!user) return failed('cancelled')
      req.login(user, (loginErr) => (loginErr ? next(loginErr) : res.redirect(returnTo)))
    })(req, res, next)
  })

  router.post('/logout', (req, res, next) => {
    req.logout((err) => {
      if (err) return next(err)
      req.session.destroy((destroyErr) => {
        if (destroyErr) return next(destroyErr)
        res.clearCookie('sr.sid').status(204).end()
      })
    })
  })

  return router
}
