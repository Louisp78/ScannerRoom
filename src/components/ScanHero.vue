<script setup lang="ts">
/**
 * Decorative hero animation: a synthetic seabed point cloud revealed by a
 * sweeping scanner beam, echoing what the pipeline does to a transect video.
 * Plain 2D canvas (no three.js) so the landing page stays light.
 */
import { onBeforeUnmount, onMounted, useTemplateRef } from 'vue'

const canvas = useTemplateRef<HTMLCanvasElement>('canvas')

/** Seabed extent in scene units: x along the transect, z across it. */
const LENGTH = 8
const WIDTH = 3.2
const POINT_COUNT = 9000
/** Seconds for the beam to sweep the whole transect once. */
const SWEEP_SECONDS = 9

interface Point {
  x: number
  y: number
  z: number
  /** Normalised height in [0, 1], drives the colour ramp. */
  h: number
}

/** Reef-like relief: rolling dunes plus a few coral heads. */
function seabedHeight(x: number, z: number): number {
  const dunes = 0.18 * Math.sin(x * 1.3) + 0.12 * Math.sin(x * 2.7 + z * 1.9)
  const heads = [
    [-2.4, 0.5, 0.55],
    [0.3, -0.7, 0.7],
    [2.6, 0.4, 0.5],
    [1.2, 1.0, 0.35],
  ].reduce(
    (sum, [cx, cz, amp]) => sum + amp! * Math.exp(-((x - cx!) ** 2 + (z - cz!) ** 2) * 1.6),
    0,
  )
  return dunes + heads
}

function buildCloud(): Point[] {
  const points: Point[] = []
  let min = Infinity
  let max = -Infinity
  for (let i = 0; i < POINT_COUNT; i++) {
    const x = (Math.random() - 0.5) * LENGTH
    const z = (Math.random() - 0.5) * WIDTH
    const y = seabedHeight(x, z) + (Math.random() - 0.5) * 0.04
    min = Math.min(min, y)
    max = Math.max(max, y)
    points.push({ x, y, z, h: 0 })
  }
  for (const p of points) p.h = (p.y - min) / (max - min)
  return points
}

/** Abyss blue -> scanner cyan -> foam white, matching the brand palette. */
function ramp(t: number): [number, number, number] {
  const stops: [number, number, number][] = [
    [22, 84, 112],
    [44, 211, 217],
    [242, 247, 247],
  ]
  const s = Math.min(Math.max(t, 0), 1) * 2
  const i = Math.min(Math.floor(s), 1)
  const f = s - i
  const a = stops[i]!
  const b = stops[i + 1]!
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]
}

let frame = 0
let resizeObserver: ResizeObserver | undefined

onMounted(() => {
  const el = canvas.value!
  const ctx = el.getContext('2d')
  if (!ctx) return
  const cloud = buildCloud()
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  let width = 0
  let height = 0

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    width = el.clientWidth
    height = el.clientHeight
    el.width = Math.round(width * dpr)
    el.height = Math.round(height * dpr)
    ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
  }
  resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(el)
  resize()

  function draw(time: number) {
    const t = time / 1000
    ctx!.clearRect(0, 0, width, height)
    // Slow orbit around the seabed, tilted to look down on it.
    const yaw = -0.5 + Math.sin(t * 0.08) * 0.25
    const pitch = 0.5
    const cy = Math.cos(yaw)
    const sy = Math.sin(yaw)
    const cp = Math.cos(pitch)
    const sp = Math.sin(pitch)
    // Sized and placed so the seabed sits beside the headline on wide screens.
    const scale = Math.min(Math.max(width * 0.1, 70), height * 0.2)
    const originX = width < 768 ? width / 2 : width * 0.64
    const originY = width < 768 ? height * 0.8 : height * 0.62
    const focal = 7
    // Beam position along the transect; it pauses briefly past the end.
    const phase = reducedMotion ? 1 : (t % SWEEP_SECONDS) / SWEEP_SECONDS
    const beamX = -LENGTH / 2 + phase * (LENGTH * 1.15)

    for (const p of cloud) {
      const ahead = p.x - beamX
      if (ahead > 0.02) continue // not scanned yet
      const glow = Math.max(0, 1 - Math.abs(ahead) / 0.35)
      const rx = p.x * cy - p.z * sy
      const rz = p.x * sy + p.z * cy
      const ry = p.y * cp - rz * sp
      const depth = p.y * sp + rz * cp + focal
      const k = focal / depth
      const sx = originX + rx * scale * k
      const sy2 = originY - ry * scale * k
      const [r, g, b] = glow > 0 ? ramp(0.55 + glow * 0.45) : ramp(p.h)
      const alpha = 0.35 + 0.5 * p.h + glow * 0.4
      ctx!.fillStyle = `rgba(${r | 0},${g | 0},${b | 0},${Math.min(alpha, 1)})`
      const size = (1.1 + glow * 1.6) * k
      ctx!.fillRect(sx, sy2, size, size)
    }

    // The beam itself: a vertical light sheet across the transect.
    if (!reducedMotion && beamX < LENGTH / 2) {
      const ends = [-WIDTH / 2, WIDTH / 2].map((z) => {
        const rx = beamX * cy - z * sy
        const rz = beamX * sy + z * cy
        const k = focal / (rz * cp + focal)
        return [originX + rx * scale * k, originY + rz * sp * scale * k] as const
      })
      const [a, b] = ends as [readonly [number, number], readonly [number, number]]
      const top = originY - scale * 2.2
      const gradient = ctx!.createLinearGradient(0, top, 0, Math.max(a[1], b[1]))
      gradient.addColorStop(0, 'rgba(44,211,217,0)')
      gradient.addColorStop(1, 'rgba(44,211,217,0.22)')
      ctx!.fillStyle = gradient
      ctx!.beginPath()
      ctx!.moveTo(a[0], top)
      ctx!.lineTo(b[0], top)
      ctx!.lineTo(b[0], b[1])
      ctx!.lineTo(a[0], a[1])
      ctx!.closePath()
      ctx!.fill()
      ctx!.strokeStyle = 'rgba(44,211,217,0.9)'
      ctx!.lineWidth = 1.5
      ctx!.beginPath()
      ctx!.moveTo(a[0], a[1])
      ctx!.lineTo(b[0], b[1])
      ctx!.stroke()
    }

    if (!reducedMotion) frame = requestAnimationFrame(draw)
  }
  frame = requestAnimationFrame(draw)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  resizeObserver?.disconnect()
})
</script>

<template>
  <canvas ref="canvas" class="h-full w-full" aria-hidden="true" />
</template>
