import { defineConfig } from 'drizzle-kit'

// `npm run db:generate` turns schema changes into a new SQL migration; the API applies pending ones when it starts.
export default defineConfig({
  dialect: 'postgresql',
  schema: './src/db/schema.ts',
  out: './drizzle',
})
