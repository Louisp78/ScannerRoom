import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { CSS2DObject, CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js'

const ABYSS = 0x0a2e44
const SCANNER = 0x2cd3d9
const FOAM = 0xf2f7f7

/** Unit sphere radius; coastlines sit slightly above it to avoid z-fighting. */
const RADIUS = 1
const COAST_RADIUS = 1.001

/** Position on the globe for WGS84 degrees, +y towards the North Pole. */
function toVector(lat: number, lon: number, radius: number): THREE.Vector3 {
  const phi = THREE.MathUtils.degToRad(lat)
  const lambda = THREE.MathUtils.degToRad(lon)
  return new THREE.Vector3(
    radius * Math.cos(phi) * Math.cos(lambda),
    radius * Math.sin(phi),
    -radius * Math.cos(phi) * Math.sin(lambda),
  )
}

interface CoastlineCollection {
  features: { geometry: { type: 'LineString'; coordinates: [number, number][] } }[]
}

/**
 * Rotating world globe with coastlines and clickable HTML pins.
 *
 * Owns the renderer, the render loop and every GPU resource; call dispose()
 * when the host element goes away.
 */
export class GlobeScene {
  private readonly renderer: THREE.WebGLRenderer
  private readonly labelRenderer = new CSS2DRenderer()
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100)
  private readonly controls: OrbitControls
  private readonly resizeObserver: ResizeObserver
  private readonly pins: CSS2DObject[] = []

  constructor(private readonly host: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setPixelRatio(window.devicePixelRatio)
    this.renderer.setClearColor(ABYSS)
    host.append(this.renderer.domElement)

    this.labelRenderer.domElement.style.position = 'absolute'
    this.labelRenderer.domElement.style.inset = '0'
    // Only the pins themselves take clicks; dragging elsewhere rotates the globe.
    this.labelRenderer.domElement.style.pointerEvents = 'none'
    host.append(this.labelRenderer.domElement)

    const ocean = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS, 96, 64),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(ABYSS).lerp(new THREE.Color(SCANNER), 0.12),
      }),
    )
    this.scene.add(ocean)

    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.controls.enablePan = false
    this.controls.enableDamping = true
    this.controls.minDistance = 1.15
    this.controls.maxDistance = 6
    this.camera.position.set(0, 0, 3.2)

    this.resizeObserver = new ResizeObserver(() => this.resize())
    this.resizeObserver.observe(host)
    this.resize()
    this.renderer.setAnimationLoop(() => this.render())
  }

  /** Draws coastlines from a GeoJSON collection of LineStrings. */
  async loadCoastlines(url: string): Promise<void> {
    const response = await fetch(url)
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`)
    const data = (await response.json()) as CoastlineCollection

    const vertices: number[] = []
    for (const { geometry } of data.features) {
      const points = geometry.coordinates
      for (let i = 1; i < points.length; i++) {
        const [lonA, latA] = points[i - 1]!
        const [lonB, latB] = points[i]!
        vertices.push(...toVector(latA, lonA, COAST_RADIUS).toArray())
        vertices.push(...toVector(latB, lonB, COAST_RADIUS).toArray())
      }
    }
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3))
    this.scene.add(
      new THREE.LineSegments(
        geometry,
        new THREE.LineBasicMaterial({ color: FOAM, transparent: true, opacity: 0.55 }),
      ),
    )
  }

  /** Anchors an HTML element (the pin) at a geographic position. */
  addPin(lat: number, lon: number, element: HTMLElement): void {
    element.style.pointerEvents = 'auto'
    const pin = new CSS2DObject(element)
    pin.position.copy(toVector(lat, lon, RADIUS))
    this.scene.add(pin)
    this.pins.push(pin)
  }

  /** Turns the globe so that the given position faces the camera. */
  lookAt(lat: number, lon: number): void {
    this.camera.position.copy(toVector(lat, lon, this.camera.position.length()))
    this.controls.update()
  }

  dispose(): void {
    this.renderer.setAnimationLoop(null)
    this.resizeObserver.disconnect()
    this.controls.dispose()
    this.scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh || obj instanceof THREE.LineSegments) {
        obj.geometry.dispose()
        ;(obj.material as THREE.Material).dispose()
      }
    })
    this.renderer.dispose()
    this.renderer.domElement.remove()
    this.labelRenderer.domElement.remove()
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
    this.controls.update()
    // Hide pins on the far side of the globe: the sphere would occlude them,
    // but HTML overlays are always drawn on top.
    for (const pin of this.pins) {
      const toCamera = this.camera.position.clone().sub(pin.position)
      pin.visible = toCamera.dot(pin.position) > 0
    }
    this.renderer.render(this.scene, this.camera)
    this.labelRenderer.render(this.scene, this.camera)
  }
}
