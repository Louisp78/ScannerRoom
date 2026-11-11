import { defineConfig } from 'drizzle-kit'

// `npm run db:generate` turns changes of src/db/schema.ts into a new SQL file
// under drizzle/; the API applies pending ones when it starts.
export default defineConfig({
  dialect: 'postgresql',
  schema: './src/db/schema.ts',
  out: './drizzle',
})
