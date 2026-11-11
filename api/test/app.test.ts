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

describe('GET /api/me/transects', () => {
  it('is 401 when signed out', async () => {
    await request(ctx.app).get('/api/me/transects').expect(401)
  })

  it("lists only the signed-in user's transects", async () => {
    const mine = await (await ctx.agentFor(owner)).get('/api/me/transects').expect(200)
    expect(mine.body.transects.map((t: { key: string }) => t.key).sort()).toEqual([
      'kona',
      'private-reef',
    ])
    expect(mine.body.transects[0]).toEqual({
      key: expect.any(String),
      showcase: expect.any(Boolean),
      createdAt: expect.any(String),
    })
    const none = await (await ctx.agentFor(other)).get('/api/me/transects').expect(200)
    expect(none.body).toEqual({ transects: [] })
  })
})

describe('GET /api/transects/:key', () => {
  it('serves a showcase transect, with its contributor, to anyone', async () => {
    const res = await request(ctx.app).get('/api/transects/kona').expect(200)
    expect(res.body).toEqual({
      key: 'kona',
      showcase: true,
      contributor: { id: owner, displayName: 'Jane Doe', orcidId: '0000-0002' },
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

describe('GET /api/users', () => {
  it('is reserved to admins', async () => {
    await request(ctx.app).get('/api/users').expect(401)
    await (await ctx.agentFor(owner)).get('/api/users').expect(403)
  })

  it('lists every user by name', async () => {
    const res = await (await ctx.agentFor(admin)).get('/api/users').expect(200)
    expect(res.body.users.map((u: { displayName: string }) => u.displayName)).toEqual([
      'Admin',
      'Bob',
      'Jane Doe',
    ])
  })
})

describe('PUT /api/transects/:key/contributor', () => {
  const put = async (userId: number, key: string, body: object, status: number) =>
    (await ctx.agentFor(userId))
      .put(`/api/transects/${key}/contributor`)
      .set(SAME_SITE)
      .send(body)
      .expect(status)

  it('lets an admin reassign a transect', async () => {
    const res = await put(admin, 'private-reef', { userId: other }, 200)
    expect(res.body.contributor).toEqual({ id: other, displayName: 'Bob', orcidId: null })
    // The new contributor may now edit it, the former one no longer.
    const editable = async (userId: number) =>
      (await (await ctx.agentFor(userId)).get('/api/transects/private-reef')).body.editable
    expect(await editable(other)).toBe(true)
    expect(await editable(owner)).toBe(false)
  })

  it('lets an admin remove the contributor', async () => {
    const res = await put(admin, 'private-reef', { userId: null }, 200)
    expect(res.body.contributor).toBeNull()
  })

  it('refuses non-admins, including the owner', async () => {
    await put(owner, 'private-reef', { userId: other }, 403)
    await request(ctx.app)
      .put('/api/transects/private-reef/contributor')
      .set(SAME_SITE)
      .send({ userId: other })
      .expect(401)
  })

  it('refuses cross-site requests', async () => {
    await (
      await ctx.agentFor(admin)
    )
      .put('/api/transects/private-reef/contributor')
      .send({ userId: other })
      .expect(403)
  })

  it('rejects unknown transects, unknown users and malformed bodies', async () => {
    await put(admin, 'nope', { userId: other }, 404)
    await put(admin, 'private-reef', { userId: 9999 }, 400)
    await put(admin, 'private-reef', { userId: 'bob' }, 400)
    await put(admin, 'private-reef', {}, 400)
  })
})

describe('GET /api/auth/check (nginx auth_request)', () => {
  const check = (key: string) => request(ctx.app).get('/api/auth/check').set('X-Transect-Key', key)

  it('lets anyone read showcase data files', async () => {
    await check('kona').expect(204)
  })

  it('refuses private data files to anonymous visitors', async () => {
    await check('private-reef').expect(401)
    await check('kona-fake').expect(401)
    await check('').expect(401)
    await request(ctx.app).get('/api/auth/check').expect(401)
  })

  it('ignores the raw request URI (dot segments must not reach the check)', async () => {
    await request(ctx.app)
      .get('/api/auth/check')
      .set('X-Original-URI', '/transects/kona/../private-reef/cloud.ply')
      .expect(401)
  })

  it('lets signed-in users read any data file', async () => {
    await (
      await ctx.agentFor(other)
    )
      .get('/api/auth/check')
      .set('X-Transect-Key', 'private-reef')
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
