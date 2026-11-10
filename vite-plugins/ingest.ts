/**
 * Local-only ingest tool: upload a transect video, run the playground pipeline on
 * it and add the resulting site to the map.
 *
 * Reconstruction runs LingBot-Map on Apple Silicon (MLX), which the VPS cannot
 * do, so these endpoints only exist on the Vite dev server (`apply: 'serve'`) and
 * never ship in the production build. The output is plain data in the repo
 * (public/transects/<key>/ and src/sites.json): committing it publishes the site.
 *
 * API, one job at a time since the reconstruction saturates the GPU:
 *   POST /__ingest/job?key&name&lat&lon&fps&start&duration  body: the raw video
 *   GET  /__ingest/job  -> IngestJob | null
 */
import { spawn } from 'node:child_process'
import { createWriteStream } from 'node:fs'
import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises'
import type { IncomingMessage, ServerResponse } from 'node:http'
import path from 'node:path'
import { pipeline } from 'node:stream/promises'
import type { Plugin } from 'vite'
import { INGEST_ROUTE, type IngestJob, type IngestStep } from '../src/ingestJob'
import type { Site } from '../src/sites'

interface IngestParams {
  key: string
  name: string
  lat: number
  lon: number
  fps: number
  start: number
  duration: number
}

const LOG_LINES = 200
const KEY_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
// LingBot-Map's temporal positional embedding is precomputed for 1024 frames.
const MAX_FRAMES = 1024

export function ingest(): Plugin {
  let root = ''
  let job: IngestJob | null = null

  const paths = () => ({
    scripts: path.join(root, 'playground/scripts'),
    video: (key: string) => path.join(root, 'playground/transects', `${key}.mp4`),
    sites: path.join(root, 'src/sites.json'),
  })

  function appendLog(chunk: string) {
    if (!job) return
    // ffmpeg redraws its progress line with \r: keep each redraw as a line.
    for (const line of chunk.split(/[\r\n]+/)) if (line.trim()) job.log.push(line)
    if (job.log.length > LOG_LINES) job.log.splice(0, job.log.length - LOG_LINES)
  }

  function runScript(script: string, key: string, env: Record<string, string> = {}) {
    return new Promise<void>((resolve, reject) => {
      const child = spawn('bash', [path.join(paths().scripts, script), key], {
        cwd: paths().scripts,
        env: { ...process.env, ...env },
      })
      child.stdout.setEncoding('utf8').on('data', appendLog)
      child.stderr.setEncoding('utf8').on('data', appendLog)
      child.on('error', reject)
      child.on('close', (code) =>
        code === 0 ? resolve() : reject(new Error(`${script} exited with code ${code}`)),
      )
    })
  }

  async function readSites(): Promise<Site[]> {
    return JSON.parse(await readFile(paths().sites, 'utf8'))
  }

  async function run(params: IngestParams) {
    const { key } = params
    const step = (s: IngestStep) => {
      if (job) job.step = s
    }
    step('extract')
    await runScript('02-extract-frames.sh', key, {
      FPS: String(params.fps),
      START: String(params.start),
      DURATION: String(params.duration),
    })
    step('reconstruct')
    await runScript('03-reconstruct.sh', key)
    step('export')
    await runScript('04-export-web.sh', key)
    step('register')
    const sites = await readSites()
    sites.push({ transectKey: key, name: params.name, lat: params.lat, lon: params.lon })
    await writeFile(paths().sites, JSON.stringify(sites, null, 2) + '\n')
  }

  async function handlePost(req: IncomingMessage, res: ServerResponse) {
    if (job?.status === 'running') return send(res, 409, { error: 'A job is already running.' })

    const params = parseParams(new URL(req.url ?? '', 'http://localhost').searchParams)
    if (typeof params === 'string') return send(res, 400, { error: params })
    if ((await readSites()).some((s) => s.transectKey === params.key)) {
      return send(res, 409, { error: `The key "${params.key}" is already on the map.` })
    }

    job = { key: params.key, name: params.name, status: 'running', step: 'upload', log: [] }
    const video = paths().video(params.key)
    try {
      await mkdir(path.dirname(video), { recursive: true })
      await pipeline(req, createWriteStream(`${video}.part`))
      await rename(`${video}.part`, video)
    } catch (e) {
      await rm(`${video}.part`, { force: true })
      fail(e)
      return send(res, 500, job)
    }
    send(res, 202, job)

    run(params).then(() => {
      if (job) job.status = 'done'
    }, fail)
  }

  function fail(e: unknown) {
    if (!job) return
    job.status = 'failed'
    job.error = e instanceof Error ? e.message : String(e)
  }

  return {
    name: 'scannerroom-ingest',
    apply: 'serve',
    configResolved(config) {
      root = config.root
    },
    configureServer(server) {
      server.middlewares.use(INGEST_ROUTE, (req, res, next) => {
        if (req.method === 'GET') return send(res, 200, job)
        if (req.method === 'POST') {
          handlePost(req, res).catch((e) => {
            fail(e)
            if (!res.headersSent) send(res, 500, job)
          })
          return
        }
        next()
      })
    },
  }
}

/** Validates the query string; returns an error message when invalid. */
function parseParams(query: URLSearchParams): IngestParams | string {
  const key = query.get('key') ?? ''
  const name = (query.get('name') ?? '').trim()
  // Number(null) is 0, so missing values must be caught before converting.
  const num = (field: string) => (query.has(field) ? Number(query.get(field)) : NaN)
  const lat = num('lat')
  const lon = num('lon')
  const fps = num('fps')
  const start = num('start')
  const duration = num('duration')

  // The key becomes a folder and file name: keep it to a safe slug.
  if (!KEY_PATTERN.test(key) || key.length > 64)
    return 'Invalid key (lowercase slug, e.g. site4-transect1).'
  if (!name || name.length > 120) return 'Name is required (120 characters max).'
  if (!(lat >= -90 && lat <= 90)) return 'Latitude must be between -90 and 90.'
  if (!(lon >= -180 && lon <= 180)) return 'Longitude must be between -180 and 180.'
  if (!(fps > 0 && fps <= 10)) return 'FPS must be between 0 and 10.'
  if (!(start >= 0)) return 'Start must be 0 or more seconds.'
  if (!(duration > 0)) return 'Duration must be more than 0 seconds.'
  if (fps * duration > MAX_FRAMES)
    return `FPS × duration must stay under ${MAX_FRAMES} frames (reconstruction limit).`
  return { key, name, lat, lon, fps, start, duration }
}

function send(res: ServerResponse, status: number, body: unknown) {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json')
  res.end(JSON.stringify(body))
}
