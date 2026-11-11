import { afterAll, beforeEach, describe, expect, it } from 'vitest'
import { IdentityConflictError } from '../src/auth/users.ts'
import { setUp } from './helpers.ts'

let ctx: Awaited<ReturnType<typeof setUp>>
beforeEach(async () => {
  await ctx?.pool.end()
  ctx = await setUp(['orcid:0000-0001'])
})
afterAll(() => ctx.pool.end())

describe('signIn', () => {
  it('creates a user on first sign-in, then finds the same one', async () => {
    const first = await ctx.users.signIn('google', { sub: 'g-1', name: 'Jane Doe' })
    const again = await ctx.users.signIn('google', { sub: 'g-1', name: 'Renamed' })
    expect(again.id).toBe(first.id)
    expect(first).toMatchObject({ displayName: 'Jane Doe', identities: ['google:g-1'] })
  })

  it('records the ORCID iD and falls back to it when the name is private', async () => {
    const user = await ctx.users.signIn('orcid', { sub: '0000-0002' })
    expect(user).toMatchObject({ orcidId: '0000-0002', displayName: 'ORCID 0000-0002' })
  })

  it('never merges accounts implicitly: another provider makes another user', async () => {
    const google = await ctx.users.signIn('google', { sub: 'g-1', name: 'Jane' })
    const orcid = await ctx.users.signIn('orcid', { sub: '0000-0002', name: 'Jane' })
    expect(orcid.id).not.toBe(google.id)
  })

  it('links a second provider to the signed-in user on request', async () => {
    const google = await ctx.users.signIn('google', { sub: 'g-1', name: 'Jane' })
    const linked = await ctx.users.signIn('orcid', { sub: '0000-0002' }, google.id)
    expect(linked.id).toBe(google.id)
    expect(linked.orcidId).toBe('0000-0002')
    expect(linked.identities.sort()).toEqual(['google:g-1', 'orcid:0000-0002'])
  })

  it('refuses to link a login that belongs to someone else', async () => {
    const jane = await ctx.users.signIn('google', { sub: 'g-1', name: 'Jane' })
    await ctx.users.signIn('orcid', { sub: '0000-0002', name: 'Bob' })
    await expect(ctx.users.signIn('orcid', { sub: '0000-0002' }, jane.id)).rejects.toThrow(
      IdentityConflictError,
    )
  })

  it('derives the admin role from ADMIN_IDENTITIES', async () => {
    expect((await ctx.users.signIn('orcid', { sub: '0000-0001' })).isAdmin).toBe(true)
    expect((await ctx.users.signIn('google', { sub: 'g-2' })).isAdmin).toBe(false)
  })
})
