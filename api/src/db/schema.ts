import { boolean, integer, pgTable, primaryKey, serial, text, timestamp } from 'drizzle-orm/pg-core'

/** A person. Logins live in user_identities: one user may sign in with ORCID or Google. */
export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  displayName: text('display_name').notNull(),
  /** Set once the user signed in with (or linked) ORCID; shown as the transect author. */
  orcidId: text('orcid_id').unique(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
})

/** One login of a user at an identity provider; `subject` is the provider's stable user id (`sub`). */
export const userIdentities = pgTable(
  'user_identities',
  {
    provider: text('provider', { enum: ['orcid', 'google'] }).notNull(),
    subject: text('subject').notNull(),
    userId: integer('user_id')
      .notNull()
      .references(() => users.id, { onDelete: 'cascade' }),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => [primaryKey({ columns: [t.provider, t.subject] })],
)

/** A reconstructed transect, i.e. a folder under public/transects/. */
export const transects = pgTable('transects', {
  key: text('key').primaryKey(),
  /** Contributor who added it; null until assigned (only admins may edit it then). */
  ownerId: integer('owner_id').references(() => users.id, { onDelete: 'set null' }),
  /** Readable without signing in, e.g. the transect embedded on the landing page. */
  showcase: boolean('showcase').notNull().default(false),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
})

// The `session` table is owned by connect-pg-simple (created on start-up), not by these migrations.
