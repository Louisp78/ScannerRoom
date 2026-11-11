import { createApp } from './app.ts'
import { createProviderStrategies } from './auth/passport.ts'
import { createUserStore } from './auth/users.ts'
import { loadConfig } from './config.ts'
import { connect, runMigrations } from './db/client.ts'
import { createTransectStore } from './transects/store.ts'

const config = loadConfig()
const { pool, db } = connect(config.databaseUrl)
await runMigrations(db)
const users = createUserStore(db, config.adminIdentities)
const strategies = await createProviderStrategies(config, users)
const providers = strategies.map((s) => s.name)
if (!providers.length) console.warn('No sign-in provider configured (ORCID_* / GOOGLE_* unset).')

const server = createApp({
  config,
  pool,
  users,
  transects: createTransectStore(db),
  strategies,
}).listen(config.port, () => {
  console.log(`API listening on :${config.port}, providers: ${providers.join(', ') || 'none'}`)
})

// Docker sends SIGTERM on stop: finish in-flight requests, then close the pool.
process.on('SIGTERM', () => server.close(() => pool.end()))
