<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import { useRouter } from 'vue-router'
import { type Site, SITES } from '@/sites'
import { GlobeScene } from '@/viewer/globeScene'

const router = useRouter()
const host = useTemplateRef<HTMLDivElement>('host')
const error = ref<string>()

let scene: GlobeScene | undefined

/** A real link, so that keyboard focus, middle-click and "open in new tab" work. */
function transectLink({ transectKey }: Site): HTMLAnchorElement {
  const to = { name: 'transect', params: { transectKey } }
  const link = document.createElement('a')
  link.href = router.resolve(to).href
  link.addEventListener('click', (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return
    event.preventDefault()
    router.push(to)
  })
  return link
}

function createDot(): HTMLSpanElement {
  const dot = document.createElement('span')
  dot.className =
    'size-4 rounded-full border-2 border-foam bg-scanner shadow-[0_0_12px_var(--color-scanner)] ' +
    'transition-[scale] group-hover:scale-150 group-focus-visible:scale-150'
  return dot
}

function createPin(site: Site): HTMLAnchorElement {
  const link = transectLink(site)
  link.title = site.name
  link.setAttribute('aria-label', `Open ${site.name}`)
  // The link is positioned by CSS2DRenderer, which rewrites its `transform`
  // every frame: it must never be transitioned, or the pin lags behind the
  // globe. Hover feedback lives on the inner dot instead. The link is also
  // larger than the dot, to give a comfortable hit area.
  link.className = PIN_CLASS
  link.append(createDot())
  return link
}

const PIN_CLASS =
  'group grid size-8 place-items-center rounded-full focus-visible:outline-2 focus-visible:outline-scanner'

/**
 * Transects filmed from the same site share its position: a single pin, with
 * the count, opens the list of them instead of stacking unreachable pins.
 */
function createGroupPin(sites: Site[]): HTMLDivElement {
  const pin = document.createElement('div')
  pin.className = 'relative'
  const button = document.createElement('button')
  button.type = 'button'
  button.className = PIN_CLASS + ' relative'
  button.setAttribute('aria-expanded', 'false')
  button.setAttribute('aria-label', `${sites.length} transects at this site`)
  button.title = `${sites.length} transects at this site`
  const count = document.createElement('span')
  count.className =
    'absolute -top-1 -right-1 rounded-full bg-foam px-1 text-[0.65rem] font-semibold text-abyss'
  count.textContent = String(sites.length)
  button.append(createDot(), count)

  const list = document.createElement('ul')
  list.hidden = true
  list.className =
    'absolute top-9 left-1/2 w-64 -translate-x-1/2 rounded-lg bg-abyss/90 p-2 text-sm text-foam shadow-lg backdrop-blur'
  for (const site of sites) {
    const link = transectLink(site)
    link.textContent = site.name
    link.className = 'block rounded px-2 py-1 hover:bg-foam/10 hover:text-scanner'
    const item = document.createElement('li')
    item.append(link)
    list.append(item)
  }
  let open = false
  const toggle = (value: boolean) => {
    open = value
    list.hidden = !open
    button.setAttribute('aria-expanded', String(open))
  }
  button.addEventListener('click', () => toggle(!open))
  pin.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') toggle(false)
  })
  pin.append(button, list)
  return pin
}

onMounted(async () => {
  scene = new GlobeScene(host.value!)
  const bySite = new Map<string, Site[]>()
  for (const site of SITES) {
    const at = `${site.lat},${site.lon}`
    bySite.set(at, [...(bySite.get(at) ?? []), site])
  }
  for (const sites of bySite.values()) {
    const { lat, lon } = sites[0]!
    scene.addPin(lat, lon, sites.length > 1 ? createGroupPin(sites) : createPin(sites[0]!))
  }
  if (SITES[0]) scene.lookAt(SITES[0].lat, SITES[0].lon)
  try {
    await scene.loadBathymetry('/geo/bathymetry.png')
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
})

onBeforeUnmount(() => scene?.dispose())
</script>

<template>
  <div class="relative h-full w-full overflow-hidden">
    <div ref="host" class="absolute inset-0" />
    <p v-if="error" class="absolute inset-x-0 bottom-4 text-center text-foam" role="alert">
      Could not load the globe: {{ error }}
    </p>
  </div>
</template>
