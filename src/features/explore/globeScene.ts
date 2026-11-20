import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { CSS2DObject, CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js'

const ABYSS = 0x0a2e44
const SCANNER = 0x2cd3d9
const FOAM = 0xf2f7f7

/** Unit sphere radius. */
const RADIUS = 1

/** Closest camera altitude (500 m over a 6371 km Earth): close enough to tell apart sites a few metres apart. */
const MIN_ALTITUDE = 500 / 6_371_000

/**
 * Sphere tessellation: at 512 x 256 segments the flat facets sag at most
 * ~120 m below the true sphere the pins sit on, small against MIN_ALTITUDE.
 */
const SPHERE_SEGMENTS = 512

/** Star shell radius: past the max orbit distance, inside the camera far plane. */
const STAR_RADIUS = 50
const STAR_COUNT = 4000

/**
 * Baked bathymetry texture: pixel = band index x scale (0 = land). The scale
 * keeps band steps large, so the GPU's 8-bit filtering precision still places
 * smooth edges between them.
 */
const BATHYMETRY_SCALE = 20

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

/**
 * Skybox of point stars uniformly spread on a distant shell, with random
 * brightness so the sky does not look like a regular grid.
 */
function createStarfield(): THREE.Points {
  const positions = new Float32Array(STAR_COUNT * 3)
  const colors = new Float32Array(STAR_COUNT * 3)
  const color = new THREE.Color()
  const point = new THREE.Vector3()
  for (let i = 0; i < STAR_COUNT; i++) {
    // Uniform direction on the sphere (avoids clustering at the poles).
    point
      .randomDirection()
      .multiplyScalar(STAR_RADIUS)
      .toArray(positions, i * 3)
    // Skew towards faint stars, a few bright ones.
    color
      .set(FOAM)
      .multiplyScalar(0.25 + 0.75 * Math.random() ** 3)
      .toArray(colors, i * 3)
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
  return new THREE.Points(
    geometry,
    new THREE.PointsMaterial({ size: 1.5, sizeAttenuation: false, vertexColors: true }),
  )
}

/**
 * Rotating world globe with bathymetry and clickable HTML pins.
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
  private readonly ocean: THREE.Mesh<THREE.SphereGeometry, THREE.Material>

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

    // Flat placeholder until loadBathymetry() swaps in the depth-band shader.
    this.ocean = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS, SPHERE_SEGMENTS, SPHERE_SEGMENTS / 2),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(ABYSS).lerp(new THREE.Color(SCANNER), 0.12),
      }),
    )
    this.scene.add(this.ocean)
    this.scene.add(createStarfield())

    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.controls.enablePan = false
    this.controls.enableDamping = true
    this.controls.minDistance = RADIUS + MIN_ALTITUDE
    this.controls.maxDistance = 6
    this.camera.position.set(0, 0, 3.2)

    this.resizeObserver = new ResizeObserver(() => this.resize())
    this.resizeObserver.observe(host)
    this.resize()
    this.renderer.setAnimationLoop(() => this.render())
  }

  /**
   * Paints the sphere from an equirectangular depth-band texture
   * (see playground/scripts/bake-bathymetry.py): flat land, shaded ocean
   * bands with a thin contour line between them, and the coastline drawn from
   * the same data so it always matches the seafloor.
   */
  async loadBathymetry(url: string): Promise<void> {
    const texture = await new THREE.TextureLoader().loadAsync(url)
    // Band indices, not colours: no colour-space conversion.
    texture.colorSpace = THREE.NoColorSpace
    texture.anisotropy = this.renderer.capabilities.getMaxAnisotropy()
    const material = new THREE.ShaderMaterial({
      uniforms: {
        depthBands: { value: texture },
        land: { value: new THREE.Color(ABYSS).lerp(new THREE.Color(FOAM), 0.14) },
        shallow: { value: new THREE.Color(ABYSS).lerp(new THREE.Color(SCANNER), 0.55) },
        deep: { value: new THREE.Color(ABYSS).multiplyScalar(0.35) },
        contour: { value: new THREE.Color(SCANNER) },
        coast: { value: new THREE.Color(FOAM) },
      },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        uniform sampler2D depthBands;
        uniform vec3 land, shallow, deep, contour, coast;
        varying vec2 vUv;
        const float DEEP_BAND = 8.0;
        void main() {
          // Filtered band index: 0 = land, 1 = 0-200 m ... 12 = deeper than 10 km.
          float depth = texture2D(depthBands, vUv).r * ${(255 / BATHYMETRY_SCALE).toFixed(4)};
          float band = floor(depth + 0.5);
          // Most of the ocean floor lies in bands 5-7: spread the ramp over the
          // first DEEP_BAND bands so trenches simply saturate at the deep colour.
          vec3 color = band < 1.0
            ? land
            : mix(shallow, deep, sqrt(clamp((band - 1.0) / (DEEP_BAND - 1.0), 0.0, 1.0)));
          // Contour where the filtered index crosses a band boundary; the
          // land/sea boundary (index 0 to 1) is the coastline.
          float x = depth - 0.5;
          float distance = min(fract(x), 1.0 - fract(x));
          float line = 1.0 - smoothstep(0.0, fwidth(x) * 1.2, distance);
          bool isCoast = depth < 1.0;
          color = mix(color, isCoast ? coast : contour, line * (isCoast ? 0.6 : 0.3));
          gl_FragColor = vec4(color, 1.0);
          #include <colorspace_fragment>
        }
      `,
    })
    this.ocean.material.dispose()
    this.ocean.material = material
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
      if (obj instanceof THREE.Mesh || obj instanceof THREE.Points) {
        obj.geometry.dispose()
        const material = obj.material as THREE.Material
        if (material instanceof THREE.ShaderMaterial) material.uniforms.depthBands?.value?.dispose()
        material.dispose()
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

  /**
   * Scales the controls and the near plane with the camera altitude, so the
   * globe stays usable from orbit down to street level.
   */
  private adaptToAltitude(): void {
    const distance = this.camera.position.length()
    const altitude = distance - RADIUS
    // Each wheel step shrinks the altitude (not the distance to the centre)
    // by a constant factor: zooming never stalls near the surface.
    this.controls.zoomSpeed = altitude / distance
    // Dragging moves the ground roughly with the cursor at every altitude.
    this.controls.rotateSpeed = Math.min(1, 0.2 * altitude)
    // Keep the near plane in front of the surface without wasting depth precision.
    const near = altitude / 2
    if (this.camera.near !== near) {
      this.camera.near = near
      this.camera.updateProjectionMatrix()
    }
  }

  private render(): void {
    this.adaptToAltitude()
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
