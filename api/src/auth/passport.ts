import * as client from 'openid-client'
import { Strategy } from 'openid-client/passport'
import { Passport } from 'passport'
import type { Config } from '../config.ts'
import type { Provider, SessionUser, UserStore } from './users.ts'

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    // `req.user` is the SessionUser loaded from the session.
    // eslint-disable-next-line @typescript-eslint/no-empty-object-type
    interface User extends SessionUser {}
  }
}

declare module 'express-session' {
  interface SessionData {
    /** Where to send the browser back after signing in (a same-site path). */
    returnTo?: string
    /** Set while the signed-in user links another provider to their account. */
    linkTo?: number
  }
}

/** A sign-in provider ready to be mounted: its name and its Passport strategy. */
export interface ProviderStrategy {
  name: Provider
  strategy: Strategy
}

/**
 * A Passport instance of its own (not the module-wide singleton), with the
 * provider strategies. The session holds only the user id; the user is
 * reloaded on each request.
 */
export function createAuthenticator(users: UserStore, strategies: readonly ProviderStrategy[]) {
  const auth = new Passport()
  auth.serializeUser<number>((user, done) => done(null, user.id))
  auth.deserializeUser<number>((id, done) => {
    // An unknown id (deleted user) yields an anonymous request, not an error.
    users.load(id).then((user) => done(null, user ?? false), done)
  })
  for (const { name, strategy } of strategies) auth.use(name, strategy)
  return auth
}

export type Authenticator = ReturnType<typeof createAuthenticator>

/**
 * Builds one openid-client strategy per configured provider (discovery needs
 * the network, hence async). The protocol
 * (discovery, PKCE, state, nonce, code exchange, ID token validation) is all
 * openid-client's; this only maps a verified login to a user.
 */
export async function createProviderStrategies(
  config: Config,
  users: UserStore,
): Promise<ProviderStrategy[]> {
  const strategies: ProviderStrategy[] = []
  for (const provider of config.providers) {
    const oidc = await client.discovery(
      provider.issuer,
      provider.clientId,
      undefined,
      // ORCID only accepts the client secret in the request body.
      client.ClientSecretPost(provider.clientSecret),
    )
    strategies.push({
      name: provider.name,
      strategy: new Strategy(
        {
          config: oidc,
          name: provider.name,
          sessionKey: `oidc:${provider.name}`,
          scope: provider.scope,
          callbackURL: new URL(`/api/auth/${provider.name}/callback`, config.publicUrl),
          passReqToCallback: true,
        },
        (req, tokens, verified) => {
          const claims = tokens.claims()
          if (!claims) return verified(new Error('The provider returned no ID token.'))
          users.signIn(provider.name, claims, req.session.linkTo).then(
            (user) => verified(null, user),
            (e: unknown) => verified(e),
          )
        },
      ),
    })
  }
  return strategies
}
