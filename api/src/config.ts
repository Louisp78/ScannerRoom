import { z } from 'zod'

import type { IdentityKey } from './contract.ts'

export type { IdentityKey }

const env = z.object({
  PORT: z.coerce.number().int().positive().default(3002),
  DATABASE_URL: z.url(),
  SESSION_SECRET: z.string().min(32, 'SESSION_SECRET must be at least 32 characters'),
  /** Public origin of the site, e.g. https://scannerroom.louisplace.com. Callback URLs and the CSRF check derive from it. */
  PUBLIC_URL: z.url(),
  /**
   * Number of reverse proxies in front of the API (Cloudflare, VPS nginx,
   * container nginx...), so that Express trusts exactly their forwarded headers.
   */
  TRUST_PROXY_HOPS: z.coerce.number().int().min(0).default(0),
  /** ORCID production (https://orcid.org) or sandbox (https://sandbox.orcid.org). */
  ORCID_ISSUER: z.url().default('https://orcid.org'),
  ORCID_CLIENT_ID: z.string().optional(),
  ORCID_CLIENT_SECRET: z.string().optional(),
  GOOGLE_CLIENT_ID: z.string().optional(),
  GOOGLE_CLIENT_SECRET: z.string().optional(),
  /** Comma-separated `provider:subject` identities granted the admin role. */
  ADMIN_IDENTITIES: z.string().default(''),
})

export interface Config {
  port: number
  databaseUrl: string
  sessionSecret: string
  publicUrl: URL
  trustProxyHops: number
  /** Cookies are marked Secure when the site is served over HTTPS. */
  secureCookies: boolean
  providers: ProviderConfig[]
  adminIdentities: ReadonlySet<IdentityKey>
}

export interface ProviderConfig {
  name: 'orcid' | 'google'
  issuer: URL
  clientId: string
  clientSecret: string
  scope: string
}

/** Reads and validates the environment; throws with every problem listed. */
export function loadConfig(source: NodeJS.ProcessEnv = process.env): Config {
  const e = env.parse(source)
  const publicUrl = new URL(e.PUBLIC_URL)
  const providers: ProviderConfig[] = []
  // A provider is enabled when its credentials are set, so a development
  // setup can run with only one of them.
  if (e.ORCID_CLIENT_ID && e.ORCID_CLIENT_SECRET)
    providers.push({
      name: 'orcid',
      issuer: new URL(e.ORCID_ISSUER),
      clientId: e.ORCID_CLIENT_ID,
      clientSecret: e.ORCID_CLIENT_SECRET,
      scope: 'openid',
    })
  if (e.GOOGLE_CLIENT_ID && e.GOOGLE_CLIENT_SECRET)
    providers.push({
      name: 'google',
      issuer: new URL('https://accounts.google.com'),
      clientId: e.GOOGLE_CLIENT_ID,
      clientSecret: e.GOOGLE_CLIENT_SECRET,
      scope: 'openid email profile',
    })
  return {
    port: e.PORT,
    databaseUrl: e.DATABASE_URL,
    sessionSecret: e.SESSION_SECRET,
    publicUrl,
    trustProxyHops: e.TRUST_PROXY_HOPS,
    secureCookies: publicUrl.protocol === 'https:',
    providers,
    adminIdentities: new Set(
      e.ADMIN_IDENTITIES.split(',')
        .map((s) => s.trim())
        .filter((s): s is IdentityKey => /^[a-z]+:.+$/.test(s)),
    ),
  }
}
