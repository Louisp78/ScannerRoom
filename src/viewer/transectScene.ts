import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js'
import { CSS2DObject, CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js'

/** Diver's camera path as written by playground/scripts/export-web.py. */
export interface TransectPath {
  video: string
  /** Camera position per extracted frame, already smoothed, reconstruction world frame. */
  positions: [number, number, number][]
  /** Camera optical axis per frame, already smoothed (unit vector): where the diver was filming. */
  forwards: [number, number, number][]
  /** Timestamp of each frame in the source video, in seconds. */
  times: number[]
}

/** Interval between time labels along the path, in seconds of video. */
const LABEL_EVERY_S = 10

const ABYSS = 0x0a2e44
const SCANNER = 0x2cd3d9

export function formatTime(seconds: number): string {
  const s = Math.round(seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/**
 * Point cloud + diver path of one reconstructed transect.
 *
 * Owns the renderer, the render loop and every GPU resource; call dispose()
 * when the host element goes away.
 */
export class TransectScene {
  private readonly renderer: THREE.WebGLRenderer
  private readonly labelRenderer = new CSS2DRenderer()
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(60, 1, 0.001, 100)
  private readonly controls: OrbitControls
  private readonly resizeObserver: ResizeObserver
  /**
   * LingBot-Map outputs OpenCV axes (x right, y down, z forward). A half turn
   * around X gives Three.js axes (y up, camera looking down -z).
   */
  private readonly world = new THREE.Group()
  /** Path tube and time ticks: hidden in the diver's-eye view. */
  private readonly pathGroup = new THREE.Group()
  private readonly diver = new THREE.Mesh()
  private readonly diverLabel: CSS2DObject
  private curve?: THREE.CatmullRomCurve3
  /** Viewing direction of each frame, reconstruction world frame. */
  private forwards: THREE.Vector3[] = []
  private timeRange: [number, number] = [0, 0]
  /** Current position on the path, as a curve parameter in [0, 1]. */
  private u = 0
  /** Camera rides the diver path instead of orbiting. */
  private following = false
  /** Orbit view saved when following starts, restored when it ends. */
  private overview?: { position: THREE.Vector3; target: THREE.Vector3 }

  /**
   * `embedded`: the viewer sits inside a scrolling page (e.g. the landing
   * page). The wheel and one-finger swipes are left to the page instead of
   * zooming/orbiting.
   */
  constructor(
    private readonly host: HTMLElement,
    { embedded = false }: { embedded?: boolean } = {},
  ) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    host.append(this.renderer.domElement)

    this.labelRenderer.domElement.style.position = 'absolute'
    this.labelRenderer.domElement.style.inset = '0'
    this.labelRenderer.domElement.style.pointerEvents = 'none'
    host.append(this.labelRenderer.domElement)

    this.scene.background = new THREE.Color(ABYSS)
    this.world.rotation.x = Math.PI
    this.scene.add(this.world)

    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.controls.enableDamping = true
    // The overview slowly turns to show the relief, until the user takes over.
    this.controls.autoRotate = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    this.controls.autoRotateSpeed = 0.6
    this.controls.addEventListener('start', () => (this.controls.autoRotate = false))
    if (embedded) {
      this.controls.enableZoom = false
      // One finger scrolls the page, two fingers orbit and pinch-zoom.
      this.controls.touches = { ONE: null, TWO: THREE.TOUCH.DOLLY_ROTATE }
      this.renderer.domElement.style.touchAction = 'pan-y'
    }

    this.diverLabel = new CSS2DObject(makeLabel('', true))
    this.diver.add(this.diverLabel)

    this.resizeObserver = new ResizeObserver(() => this.resize())
    this.resizeObserver.observe(host)
    this.resize()
    this.renderer.setAnimationLoop(() => this.render())
  }

  /**
   * Loads the transect assets; resolves with the video time range of the path
   * and the URL of the web copy of the video.
   */
  async load(
    baseUrl: string,
    onProgress?: (ratio: number) => void,
  ): Promise<{ range: [number, number]; videoUrl: string }> {
    const [cloud, path] = await Promise.all([
      new PLYLoader().loadAsync(`${baseUrl}/cloud.ply`, (e) => {
        if (e.lengthComputable) onProgress?.(e.loaded / e.total)
      }),
      fetch(`${baseUrl}/path.json`).then((r) => {
        if (!r.ok) throw new Error(`path.json: HTTP ${r.status}`)
        return r.json() as Promise<TransectPath>
      }),
    ])

    cloud.computeBoundingSphere()
    const radius = cloud.boundingSphere!.radius
    // Roughly voxel-sized points: closes the gaps without blurring the reef.
    const points = new THREE.Points(
      cloud,
      new THREE.PointsMaterial({ size: radius / 300, vertexColors: true }),
    )
    this.world.add(points)

    this.addPath(path, radius)
    this.frame(cloud)
    return { range: this.timeRange, videoUrl: `${baseUrl}/${path.video}` }
  }

  /** Moves the diver marker to a given time of the video. */
  setTime(seconds: number): void {
    if (!this.curve) return
    const [t0, t1] = this.timeRange
    // Frames are evenly spaced in time and CatmullRomCurve3.getPoint maps its
    // parameter linearly onto the control points, so time maps linearly too.
    this.u = THREE.MathUtils.clamp((seconds - t0) / (t1 - t0), 0, 1)
    this.diver.position.copy(this.curve.getPoint(this.u))
    this.diverLabel.element.textContent = formatTime(seconds)
    if (this.following) this.placeCameraOnPath(this.u)
  }

  /**
   * Switches between the diver's-eye view (camera on the path, orbit disabled)
   * and the free orbit view, which is restored as it was left.
   */
  setFollow(on: boolean): void {
    if (on === this.following || !this.curve) return
    this.following = on
    this.controls.enabled = !on
    // Path, ticks and marker would sit right in front of the lens; the
    // slider already shows the time.
    this.pathGroup.visible = !on
    this.diver.visible = !on
    this.diverLabel.visible = !on
    this.pathGroup.traverse((obj) => {
      if (obj instanceof CSS2DObject) obj.visible = !on
    })
    if (on) {
      this.overview = {
        position: this.camera.position.clone(),
        target: this.controls.target.clone(),
      }
      this.placeCameraOnPath(this.u)
    } else if (this.overview) {
      this.camera.position.copy(this.overview.position)
      this.controls.target.copy(this.overview.target)
      this.controls.update()
    }
  }

  /** Puts the camera at the diver's eye, looking where the diver was filming. */
  private placeCameraOnPath(u: number): void {
    const eye = this.curve!.getPoint(u)
    // Viewing direction interpolated between the two surrounding frames.
    const f = u * (this.forwards.length - 1)
    const i = Math.min(Math.floor(f), this.forwards.length - 2)
    const forward = this.forwards[i]!.clone().lerp(this.forwards[i + 1]!, f - i)
    const target = eye.clone().add(forward)
    this.world.updateMatrixWorld()
    // camera.up stays world up: the horizon is kept level, without the diver's roll.
    this.camera.position.copy(eye.applyMatrix4(this.world.matrixWorld))
    this.camera.lookAt(target.applyMatrix4(this.world.matrixWorld))
  }

  dispose(): void {
    this.renderer.setAnimationLoop(null)
    this.resizeObserver.disconnect()
    this.controls.dispose()
    this.scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh || obj instanceof THREE.Points) {
        obj.geometry.dispose()
        ;(obj.material as THREE.Material).dispose()
      }
    })
    this.renderer.dispose()
    this.renderer.domElement.remove()
    this.labelRenderer.domElement.remove()
  }

  private addPath(path: TransectPath, sceneRadius: number): void {
    // Smoothing is done by the export script; the spline only interpolates.
    this.forwards = path.forwards.map((f) => new THREE.Vector3(...f))
    this.curve = new THREE.CatmullRomCurve3(
      path.positions.map((p) => new THREE.Vector3(...p)),
      false,
      'centripetal',
    )
    this.timeRange = [path.times[0]!, path.times[path.times.length - 1]!]

    const tubeRadius = sceneRadius / 400
    const tube = new THREE.Mesh(
      new THREE.TubeGeometry(this.curve, path.positions.length * 8, tubeRadius, 8, false),
      new THREE.MeshBasicMaterial({ color: SCANNER, transparent: true, opacity: 0.85 }),
    )
    this.pathGroup.add(tube)
    this.world.add(this.pathGroup)

    // Time ticks every LABEL_EVERY_S seconds, plus the end of the path. The
    // start gets none: the diver marker sits there and already shows the time.
    const [t0, t1] = this.timeRange
    const tickGeometry = new THREE.SphereGeometry(tubeRadius * 2.5, 12, 8)
    const tickMaterial = new THREE.MeshBasicMaterial({ color: SCANNER })
    const ticks: number[] = []
    for (let t = (Math.floor(t0 / LABEL_EVERY_S) + 1) * LABEL_EVERY_S; t < t1; t += LABEL_EVERY_S)
      ticks.push(t)
    ticks.push(t1)
    for (const t of ticks) {
      const tick = new THREE.Mesh(tickGeometry, tickMaterial)
      tick.position.copy(this.curve.getPoint((t - t0) / (t1 - t0)))
      tick.add(new CSS2DObject(makeLabel(formatTime(t), false)))
      this.pathGroup.add(tick)
    }

    this.diver.geometry = new THREE.SphereGeometry(tubeRadius * 5, 16, 12)
    this.diver.material = new THREE.MeshBasicMaterial({ color: 0xffffff })
    this.world.add(this.diver)
    this.setTime(t0)
  }

  /**
   * Frames the diver's path rather than the cloud, whose bounding box is
   * inflated by a few far-away streaks. The camera stands beside the path, on
   * the side holding fewer points (open water), so the path sits in front of
   * the reef instead of behind it.
   */
  private frame(cloud: THREE.BufferGeometry): void {
    if (!this.curve) return
    this.world.updateMatrixWorld()
    const toScene = (v: THREE.Vector3) => v.applyMatrix4(this.world.matrixWorld)
    const start = toScene(this.curve.getPoint(0))
    const end = toScene(this.curve.getPoint(1))
    const middle = toScene(this.curve.getPoint(0.5))
    const length = start.distanceTo(end)

    const up = new THREE.Vector3(0, 1, 0)
    const side = end.clone().sub(start).setY(0).cross(up).normalize()
    if (pointsOnSide(cloud, this.world.matrixWorld, middle, side) > 0.5) side.negate()
    this.camera.position
      .copy(middle)
      .addScaledVector(side, length * 0.8)
      .addScaledVector(up, length * 0.35)
    this.controls.target.copy(middle)
    this.controls.update()
  }

  private resize(): void {
    const { clientWidth: w, clientHeight: h } = this.host
    if (!w || !h) return
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
    this.renderer.setSize(w, h)
    this.labelRenderer.setSize(w, h)
  }

  private render(): void {
    // OrbitControls.update() re-aims the camera at its target even when
    // disabled, which would fight the diver's-eye view.
    if (!this.following) this.controls.update()
    this.renderer.render(this.scene, this.camera)
    this.labelRenderer.render(this.scene, this.camera)
  }
}

/** Share of the points lying on the `normal` side of the plane through `origin`. */
function pointsOnSide(
  geometry: THREE.BufferGeometry,
  matrix: THREE.Matrix4,
  origin: THREE.Vector3,
  normal: THREE.Vector3,
): number {
  const pos = geometry.getAttribute('position')
  const p = new THREE.Vector3()
  const STRIDE = 50 // a 2 % sample is plenty to tell the sides apart
  let ahead = 0
  let total = 0
  for (let i = 0; i < pos.count; i += STRIDE, total++) {
    p.fromBufferAttribute(pos, i).applyMatrix4(matrix)
    if (p.sub(origin).dot(normal) > 0) ahead++
  }
  return ahead / total
}

function makeLabel(text: string, highlighted: boolean): HTMLElement {
  const el = document.createElement('div')
  el.textContent = text
  el.className = highlighted
    ? '-translate-y-6 rounded bg-foam px-1.5 py-0.5 text-xs font-semibold text-abyss'
    : '-translate-y-4 rounded bg-abyss/70 px-1 text-[0.7rem] text-scanner'
  return el
}
