import request from 'supertest'
import { afterAll, beforeEach, describe, expect, it } from 'vitest'
import { safeReturnTo } from '../src/auth/routes.ts'
import { transects } from '../src/db/schema.ts'
import { SAME_SITE, setUp } from './helpers.ts'

let ctx: Awaited<ReturnType<typeof setUp>>
let owner: number
let other: number
let admin: number

beforeEach(async () => {
  await ctx?.pool.end()
  ctx = await setUp(['orcid:0000-0001'])
  owner = (await ctx.users.signIn('orcid', { sub: '0000-0002', name: 'Jane Doe' })).id
  other = (await ctx.users.signIn('google', { sub: 'g-1', name: 'Bob' })).id
  admin = (await ctx.users.signIn('orcid', { sub: '0000-0001', name: 'Admin' })).id
  await ctx.db
    .insert(transects)
    .values([
      { key: 'kona', ownerId: owner, showcase: true },
      { key: 'private-reef', ownerId: owner },
      { key: 'orphan' },
    ])
})
afterAll(() => ctx.pool.end())

describe('GET /api/me', () => {
  it('is 401 when signed out', async () => {
    await request(ctx.app).get('/api/me').expect(401)
  })

  it('returns the signed-in user', async () => {
    const agent = await ctx.agentFor(owner)
    const res = await agent.get('/api/me').expect(200)
    expect(res.body).toMatchObject({
      displayName: 'Jane Doe',
      orcidId: '0000-0002',
      isAdmin: false,
    })
  })
})

describe('GET /api/transects/:key', () => {
  it('serves a showcase transect, with its contributor, to anyone', async () => {
    const res = await request(ctx.app).get('/api/transects/kona').expect(200)
    expect(res.body).toEqual({
      key: 'kona',
      showcase: true,
      contributor: { displayName: 'Jane Doe', orcidId: '0000-0002' },
      editable: false,
    })
  })

  it('answers 401 to anonymous visitors for private and unknown transects alike', async () => {
    await request(ctx.app).get('/api/transects/private-reef').expect(401)
    await request(ctx.app).get('/api/transects/nope').expect(401)
  })

  it('tells who may edit: owner and admin, not other contributors', async () => {
    const editable = async (userId: number, key: string) =>
      (await (await ctx.agentFor(userId)).get(`/api/transects/${key}`).expect(200)).body.editable
    expect(await editable(owner, 'private-reef')).toBe(true)
    expect(await editable(other, 'private-reef')).toBe(false)
    expect(await editable(admin, 'private-reef')).toBe(true)
    // No owner yet: admins only.
    expect(await editable(other, 'orphan')).toBe(false)
    expect(await editable(admin, 'orphan')).toBe(true)
  })

  it('is 404 for an unknown transect once signed in', async () => {
    await (await ctx.agentFor(other)).get('/api/transects/nope').expect(404)
  })
})

describe('GET /api/auth/check (nginx auth_request)', () => {
  const check = (uri: string) => request(ctx.app).get('/api/auth/check').set('X-Original-URI', uri)

  it('lets anyone read showcase data files', async () => {
    await check('/transects/kona/cloud.ply').expect(204)
  })

  it('refuses private data files to anonymous visitors', async () => {
    await check('/transects/private-reef/cloud.ply').expect(401)
    await check('/transects/kona-fake/cloud.ply').expect(401)
    await check('/transects/%E0%A4%A/cloud.ply').expect(401)
    await check('').expect(401)
  })

  it('lets signed-in users read any data file', async () => {
    await (
      await ctx.agentFor(other)
    )
      .get('/api/auth/check')
      .set('X-Original-URI', '/transects/private-reef/cloud.ply')
      .expect(204)
  })
})

describe('POST /api/auth/logout', () => {
  it('refuses cross-site requests', async () => {
    const agent = await ctx.agentFor(owner)
    await agent.post('/api/auth/logout').expect(403)
    await agent
      .post('/api/auth/logout')
      .set({ ...SAME_SITE, Origin: 'https://evil.example' })
      .expect(403)
    await agent.get('/api/me').expect(200)
  })

  it('ends the session', async () => {
    const agent = await ctx.agentFor(owner)
    await agent.post('/api/auth/logout').set(SAME_SITE).expect(204)
    await agent.get('/api/me').expect(401)
  })
})

describe('sign-in', () => {
  it('lists the configured providers', async () => {
    const res = await request(ctx.app).get('/api/auth/providers').expect(200)
    expect(res.body).toEqual({ providers: [] })
  })

  it('rejects an unconfigured provider', async () => {
    await request(ctx.app).get('/api/auth/orcid').expect(404)
  })

  it('only returns to same-site paths', () => {
    expect(safeReturnTo('/transects/kona')).toBe('/transects/kona')
    expect(safeReturnTo('//evil.example')).toBe('/explore')
    expect(safeReturnTo('/\\evil.example')).toBe('/explore')
    expect(safeReturnTo('https://evil.example')).toBe('/explore')
    expect(safeReturnTo(undefined)).toBe('/explore')
  })
})
