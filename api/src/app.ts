import connectPgSimple from 'connect-pg-simple'
import express, { type ErrorRequestHandler, type Express } from 'express'
import rateLimit from 'express-rate-limit'
import session from 'express-session'
import helmet from 'helmet'
import type pg from 'pg'
import type { Config } from './config.ts'
import type { Db } from './db/client.ts'
import { csrfCheck, HttpError } from './auth/guards.ts'
import { createAuthenticator, type ProviderStrategy } from './auth/passport.ts'
import { authRouter } from './auth/routes.ts'
import type { UserStore } from './auth/users.ts'
import { transectsRouter } from './routes/transects.ts'

/**
 * Session lifetime, counted from sign-in. Not extended on activity: nginx asks
 * /api/auth/check for every data file (video chunks included), and refreshing
 * the session each time would mean a database write per request.
 */
const SESSION_MAX_AGE_MS = 30 * 24 * 3600 * 1000

export interface AppDeps {
  config: Config
  db: Db
  pool: pg.Pool
  users: UserStore
  strategies: readonly ProviderStrategy[]
  /** Test-only hook, mounted after sessions and before the routes. */
  beforeRoutes?: (app: Express) => void
}

export function createApp({ config, db, pool, users, strategies, beforeRoutes }: AppDeps): Express {
  const app = express()
  app.set('trust proxy', config.trustProxyHops)
  app.disable('x-powered-by')
  app.use(helmet())
  app.use(express.json({ limit: '100kb' }))

  const PgStore = connectPgSimple(session)
  app.use(
    session({
      name: 'sr.sid',
      store: new PgStore({ pool, createTableIfMissing: true, disableTouch: true }),
      secret: config.sessionSecret,
      resave: false,
      saveUninitialized: false,
      // The API is only reachable through the site's nginx: trust its
      // X-Forwarded-Proto to decide whether the Secure cookie can be sent.
      proxy: true,
      cookie: {
        httpOnly: true,
        secure: config.secureCookies,
        sameSite: 'lax',
        maxAge: SESSION_MAX_AGE_MS,
      },
    }),
  )
  const auth = createAuthenticator(users, strategies)
  app.use(auth.initialize())
  app.use(auth.session())
  app.use('/api', csrfCheck(config.publicUrl))
  beforeRoutes?.(app)

  const transects = transectsRouter(db)

  /**
   * nginx `auth_request` target guarding the transect data files
   * (/transects/<key>/*). nginx passes the original URI; showcase transects
   * stay readable without a session.
   */
  app.get('/api/auth/check', async (req, res) => {
    if (req.user) return res.status(204).end()
    const key = /^\/transects\/([^/?#]+)\//.exec(req.get('x-original-uri') ?? '')?.[1]
    let allowed = false
    try {
      allowed = key !== undefined && (await transects.isShowcase(decodeURIComponent(key)))
    } catch (e) {
      if (!(e instanceof URIError)) throw e
    }
    res.status(allowed ? 204 : 401).end()
  })
  // Sign-in attempts are cheap to make and expensive to serve (provider round
  // trips). Registered after /check, which nginx calls for every data file.
  app.use('/api/auth', rateLimit({ windowMs: 60_000, limit: 30, standardHeaders: 'draft-8' }))
  app.use(
    '/api/auth',
    authRouter(
      auth,
      strategies.map((s) => s.name),
    ),
  )

  app.get('/api/me', (req, res) => {
    if (!req.user) throw new HttpError(401, 'Sign in required.')
    res.json(req.user)
  })
  app.use('/api/transects', transects.router)

  app.use('/api', (_req, _res, next) => next(new HttpError(404, 'Not found.')))
  const onError: ErrorRequestHandler = (err, _req, res, _next) => {
    if (err instanceof HttpError) return res.status(err.status).json({ error: err.message })
    console.error(err)
    res.status(500).json({ error: 'Internal error.' })
  }
  app.use(onError)
  return app
}
