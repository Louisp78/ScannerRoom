<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import { useRouter } from 'vue-router'
import { SITES } from '@/sites'
import { GlobeScene } from '@/viewer/globeScene'

const router = useRouter()
const host = useTemplateRef<HTMLDivElement>('host')
const error = ref<string>()

let scene: GlobeScene | undefined

/** A real link, so that keyboard focus, middle-click and "open in new tab" work. */
function createPin(transectKey: string, name: string): HTMLAnchorElement {
  const to = { name: 'transect', params: { transectKey } }
  const link = document.createElement('a')
  link.href = router.resolve(to).href
  link.title = name
  link.setAttribute('aria-label', `Ouvrir ${name}`)
  // The link is positioned by CSS2DRenderer, which rewrites its `transform`
  // every frame: it must never be transitioned, or the pin lags behind the
  // globe. Hover feedback lives on the inner dot instead. The link is also
  // larger than the dot, to give a comfortable hit area.
  link.className =
    'group grid size-8 place-items-center rounded-full focus-visible:outline-2 focus-visible:outline-scanner'
  const dot = document.createElement('span')
  dot.className =
    'size-4 rounded-full border-2 border-foam bg-scanner shadow-[0_0_12px_var(--color-scanner)] ' +
    'transition-[scale] group-hover:scale-150 group-focus-visible:scale-150'
  link.append(dot)
  link.addEventListener('click', (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return
    event.preventDefault()
    router.push(to)
  })
  return link
}

onMounted(async () => {
  scene = new GlobeScene(host.value!)
  for (const site of SITES) scene.addPin(site.lat, site.lon, createPin(site.transectKey, site.name))
  if (SITES[0]) scene.lookAt(SITES[0].lat, SITES[0].lon)
  try {
    await scene.loadCoastlines('/geo/coastline-110m.geojson')
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
      Impossible de charger les côtes : {{ error }}
    </p>
  </div>
</template>
