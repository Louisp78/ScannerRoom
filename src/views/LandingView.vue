<script setup lang="ts">
import { defineAsyncComponent, onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import type { Directive } from 'vue'
import ScanHero from '@/components/ScanHero.vue'
import { formatLatLon, type Site, SITES } from '@/sites'

/**
 * Fades an element in the first time it scrolls into view. Elements start
 * visible when IntersectionObserver is missing or motion is reduced (see CSS).
 */
const vReveal: Directive<HTMLElement, number | undefined> = {
  mounted(el, binding) {
    if (!('IntersectionObserver' in window)) return
    el.classList.add('reveal')
    el.style.setProperty('--reveal-delay', `${binding.value ?? 0}ms`)
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return
        el.classList.add('revealed')
        observer.disconnect()
      },
      { threshold: 0.2 },
    )
    observer.observe(el)
  },
}

const steps = [
  {
    title: 'Film',
    text: 'Swim your transect with any action camera. A geolocated video is all the field kit you need.',
  },
  {
    title: 'Reconstruct',
    text: 'Frames are extracted and a learned dense reconstruction recovers per-frame depth and the camera trajectory.',
  },
  {
    title: 'Clean',
    text: 'Low-confidence depth and open water are filtered out, the cloud is voxelised relative to median depth, outliers removed.',
  },
  {
    title: 'Explore',
    text: 'The coloured point cloud and camera path stream to the browser: scroll along the reef as if you were diving it.',
  },
]

const features = [
  {
    title: 'Open, standard formats',
    text: 'Point clouds ship as PLY and camera paths as JSON. Load them straight into CloudCompare, Open3D or your own scripts.',
    roadmap: false,
  },
  {
    title: 'Reproducible by design',
    text: 'One generic pipeline for every transect. No per-site tuning: every threshold is derived from the data itself.',
    roadmap: false,
  },
  {
    title: 'Geolocated and comparable',
    text: 'Each reconstruction is pinned on a shared world map, next to transects filmed by other teams.',
    roadmap: false,
  },
  {
    title: 'Metrics on demand',
    text: 'Rugosity, relief and benthic cover computed from the 3D model, ready for your analyses.',
    roadmap: true,
  },
  {
    title: 'Editable models',
    text: 'Crop, annotate and correct reconstructions, then share the curated version with the community.',
    roadmap: true,
  },
  {
    title: 'Change over time',
    text: 'Revisit a site, re-film the same transect and compare reconstructions to follow how the reef evolves.',
    roadmap: true,
  },
]

/**
 * Atlas pins, one per group of sites that would overlap on the flat map: its
 * 24 px pins span ~16° on a ~530 px wide map, so nearby sites (the transects of
 * a reef, the sites of a coast) share one pin with their count, which opens the
 * globe where they separate when zooming in.
 */
const ATLAS_PIN_DEG = 16
const atlasPins = SITES.reduce<{ lat: number; lon: number; sites: Site[] }[]>((pins, site) => {
  const pin = pins.find((p) => Math.hypot(p.lat - site.lat, p.lon - site.lon) < ATLAS_PIN_DEG / 2)
  if (pin) pin.sites.push(site)
  else pins.push({ lat: site.lat, lon: site.lon, sites: [site] })
  return pins
}, [])

/** Reconstruction showcased on the landing page, as a real example of the output. */
const featured = SITES.find((site) => site.transectKey === 'site3-transect2-south-return')

// three.js and the ~20 MB point cloud only load once the showcase nears the
// viewport (US-2.3), so the top of the landing page stays light.
const TransectViewer = defineAsyncComponent(() => import('@/components/TransectViewer.vue'))
const showcase = useTemplateRef<HTMLElement>('showcase')
const showcaseActive = ref(false)
let showcaseObserver: IntersectionObserver | undefined

onMounted(() => {
  if (!showcase.value) return
  showcaseObserver = new IntersectionObserver(
    ([entry]) => {
      if (!entry?.isIntersecting) return
      showcaseActive.value = true
      showcaseObserver?.disconnect()
    },
    { rootMargin: '400px 0px' },
  )
  showcaseObserver.observe(showcase.value)
})
onBeforeUnmount(() => showcaseObserver?.disconnect())
</script>

<template>
  <div class="overflow-x-hidden">
    <!-- Hero -->
    <section class="relative isolate flex min-h-svh flex-col">
      <div
        class="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_50%_120%,rgb(44_211_217/0.18),transparent_60%)]"
      />
      <div class="absolute inset-0 -z-10 opacity-90">
        <ScanHero />
      </div>
      <div
        class="absolute inset-x-0 bottom-0 -z-10 h-40 bg-gradient-to-t from-abyss to-transparent"
      />

      <header class="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <span class="flex items-center gap-2 font-semibold tracking-wide text-scanner">
          <span class="relative flex size-2.5">
            <span
              class="absolute inline-flex size-full animate-ping rounded-full bg-scanner opacity-60 motion-reduce:animate-none"
            />
            <span class="relative inline-flex size-2.5 rounded-full bg-scanner" />
          </span>
          ScannerRoom
        </span>
        <RouterLink
          to="/explore"
          class="rounded-full border border-scanner/40 px-4 py-1.5 text-sm text-scanner transition-colors hover:bg-scanner/10 focus-visible:outline-2 focus-visible:outline-scanner"
        >
          Open the atlas
        </RouterLink>
      </header>

      <div
        class="mx-auto flex w-full max-w-6xl flex-1 flex-col justify-start px-4 pt-[8vh] sm:px-6"
      >
        <p
          class="hero-in mb-4 text-xs font-medium tracking-[0.25em] text-scanner uppercase"
          style="--delay: 0ms"
        >
          For marine scientists &amp; reef researchers
        </p>
        <h1
          class="hero-in max-w-3xl text-4xl leading-tight font-semibold text-balance sm:text-6xl"
          style="--delay: 120ms"
        >
          Turn a transect video into a
          <span class="bg-gradient-to-r from-scanner to-foam bg-clip-text text-transparent">
            3D seabed you can study.
          </span>
        </h1>
        <p class="hero-in mt-6 max-w-xl text-base text-foam/75 sm:text-lg" style="--delay: 240ms">
          ScannerRoom reconstructs your dive footage into a geolocated, exportable 3D model and
          places it in a shared world atlas, alongside transects filmed by researchers everywhere.
        </p>
        <div class="hero-in mt-8 flex flex-wrap gap-3" style="--delay: 360ms">
          <RouterLink
            to="/explore"
            class="rounded-full bg-scanner px-6 py-3 font-semibold text-abyss shadow-[0_0_30px_rgb(44_211_217/0.35)] transition hover:shadow-[0_0_45px_rgb(44_211_217/0.6)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foam"
          >
            Explore the atlas
          </RouterLink>
          <a
            href="#pipeline"
            class="rounded-full border border-foam/25 px-6 py-3 font-semibold text-foam transition-colors hover:border-foam/60 focus-visible:outline-2 focus-visible:outline-scanner"
          >
            How it works
          </a>
        </div>
      </div>

      <a
        href="#pipeline"
        class="mx-auto mb-6 flex flex-col items-center gap-2 text-xs tracking-widest text-foam/50 uppercase"
        aria-label="Scroll to how it works"
      >
        Dive in
        <span class="h-10 w-px animate-pulse bg-gradient-to-b from-scanner to-transparent" />
      </a>
    </section>

    <!-- Pipeline -->
    <section id="pipeline" class="mx-auto max-w-6xl scroll-mt-8 px-4 py-24 sm:px-6">
      <div v-reveal class="max-w-2xl">
        <p class="text-xs font-medium tracking-[0.25em] text-scanner uppercase">
          From dive to dataset
        </p>
        <h2 class="mt-3 text-3xl font-semibold sm:text-4xl">Four steps, zero manual modelling.</h2>
        <p class="mt-4 text-foam/70">
          The same automated pipeline processes every upload, so models from different teams and
          different years stay comparable.
        </p>
      </div>
      <div class="relative mt-14">
        <div
          v-reveal
          class="scan-line absolute top-5 right-[12%] left-[12%] hidden h-px bg-scanner/60 md:block"
          aria-hidden="true"
        />
        <ol class="grid gap-6 md:grid-cols-4">
          <li v-for="(step, i) in steps" :key="step.title" v-reveal="150 * i" class="relative">
            <span
              class="relative grid size-10 place-items-center rounded-full border border-scanner/50 bg-abyss font-mono text-sm text-scanner shadow-[0_0_20px_rgb(44_211_217/0.25)]"
            >
              {{ String(i + 1).padStart(2, '0') }}
            </span>
            <h3 class="mt-5 text-lg font-semibold">{{ step.title }}</h3>
            <p class="mt-2 text-sm leading-relaxed text-foam/70">{{ step.text }}</p>
          </li>
        </ol>
      </div>
    </section>

    <!-- Showcase: a real reconstruction -->
    <section v-if="featured" class="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
      <div v-reveal class="flex flex-wrap items-end justify-between gap-6">
        <div class="max-w-2xl">
          <p class="text-xs font-medium tracking-[0.25em] text-scanner uppercase">
            Real data, live in your browser
          </p>
          <h2 class="mt-3 text-3xl font-semibold sm:text-4xl">Dive a reconstructed reef.</h2>
          <p class="mt-4 text-foam/70">
            This transect was filmed off the Kona coast of Hawaiʻi and reconstructed by the pipeline
            above with no manual touch-up. Drag to orbit, then press play to swim the diver's path
            with the source footage in sync.
          </p>
        </div>
        <RouterLink
          :to="{ name: 'transect', params: { transectKey: featured.transectKey } }"
          class="inline-flex items-center gap-2 font-semibold text-scanner hover:underline focus-visible:outline-2 focus-visible:outline-scanner"
        >
          Open full screen <span aria-hidden="true">↗</span>
        </RouterLink>
      </div>

      <div v-reveal="150" class="showcase-frame relative mt-10 rounded-3xl p-px">
        <div
          ref="showcase"
          class="relative aspect-[4/5] overflow-hidden rounded-3xl bg-abyss sm:aspect-[16/9]"
        >
          <TransectViewer
            v-if="showcaseActive"
            :base-url="`/transects/${featured.transectKey}`"
            :site="featured"
            embedded
          />
        </div>
      </div>
      <ul
        v-reveal="250"
        class="mt-6 flex flex-wrap justify-center gap-x-8 gap-y-2 text-xs tracking-wider text-foam/55 uppercase"
      >
        <li><span class="text-scanner" aria-hidden="true">◆</span> Coloured point cloud (PLY)</li>
        <li><span class="text-scanner" aria-hidden="true">◆</span> Smoothed diver path (JSON)</li>
        <li><span class="text-scanner" aria-hidden="true">◆</span> Source video, time-synced</li>
      </ul>
    </section>

    <!-- Features -->
    <section class="relative py-24">
      <div
        class="absolute inset-0 -z-10 bg-[linear-gradient(180deg,transparent,rgb(44_211_217/0.05)_30%,rgb(44_211_217/0.05)_70%,transparent)]"
      />
      <div class="mx-auto max-w-6xl px-4 sm:px-6">
        <div v-reveal class="max-w-2xl">
          <p class="text-xs font-medium tracking-[0.25em] text-scanner uppercase">
            Built for research
          </p>
          <h2 class="mt-3 text-3xl font-semibold sm:text-4xl">
            A model you can measure, edit and cite.
          </h2>
        </div>
        <ul class="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <li
            v-for="(feature, i) in features"
            :key="feature.title"
            v-reveal="80 * (i % 3)"
            class="group relative overflow-hidden rounded-2xl border border-foam/10 bg-foam/[0.03] p-6 transition-colors hover:border-scanner/40"
          >
            <span
              class="card-sweep pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 bg-gradient-to-r from-transparent via-scanner/10 to-transparent"
              aria-hidden="true"
            />
            <div class="flex items-start justify-between gap-3">
              <h3 class="font-semibold">{{ feature.title }}</h3>
              <span
                v-if="feature.roadmap"
                class="shrink-0 rounded-full border border-foam/20 px-2 py-0.5 text-[10px] tracking-wider text-foam/60 uppercase"
              >
                Roadmap
              </span>
            </div>
            <p class="mt-3 text-sm leading-relaxed text-foam/70">{{ feature.text }}</p>
          </li>
        </ul>
      </div>
    </section>

    <!-- Shared atlas -->
    <section class="mx-auto grid max-w-6xl items-center gap-12 px-4 py-24 sm:px-6 md:grid-cols-2">
      <div v-reveal>
        <p class="text-xs font-medium tracking-[0.25em] text-scanner uppercase">One shared atlas</p>
        <h2 class="mt-3 text-3xl font-semibold sm:text-4xl">
          Your transect joins a world dataset.
        </h2>
        <p class="mt-4 text-foam/70">
          Every reconstruction is geolocated on a common globe. Compare your site with reefs filmed
          on the other side of the planet, reuse others' transects, and help build an open, growing
          map of the world's coastal seabeds.
        </p>
        <RouterLink
          to="/explore"
          class="mt-8 inline-flex items-center gap-2 font-semibold text-scanner hover:underline focus-visible:outline-2 focus-visible:outline-scanner"
        >
          Browse the {{ SITES.length }} published transects <span aria-hidden="true">→</span>
        </RouterLink>
      </div>
      <div
        v-reveal="150"
        class="relative aspect-[2/1] w-full overflow-hidden rounded-2xl border border-scanner/20 bg-abyss shadow-[0_0_60px_rgb(44_211_217/0.08)]"
      >
        <!-- Equirectangular bathymetry (land is black) used as a luminance mask: oceans glow. -->
        <div class="atlas-ocean absolute inset-0" aria-hidden="true" />
        <span class="atlas-sweep absolute inset-y-0 w-px bg-scanner/70" aria-hidden="true" />
        <ul class="absolute inset-0">
          <li
            v-for="pin in atlasPins"
            :key="pin.sites[0]!.transectKey"
            class="absolute"
            :style="{
              left: `${((pin.lon + 180) / 360) * 100}%`,
              top: `${((90 - pin.lat) / 180) * 100}%`,
            }"
          >
            <RouterLink
              :to="
                pin.sites.length > 1
                  ? '/explore'
                  : { name: 'transect', params: { transectKey: pin.sites[0]!.transectKey } }
              "
              :aria-label="
                pin.sites.length > 1
                  ? `${pin.sites.length} transects around ${formatLatLon(pin)}: open the globe`
                  : `Open ${pin.sites[0]!.name}`
              "
              class="group absolute grid size-6 -translate-1/2 place-items-center rounded-full focus-visible:outline-2 focus-visible:outline-scanner"
            >
              <span
                class="absolute size-3 animate-ping rounded-full bg-scanner/50 motion-reduce:animate-none"
              />
              <span
                class="relative size-2.5 rounded-full border border-foam bg-scanner shadow-[0_0_10px_var(--color-scanner)] transition-[scale] group-hover:scale-150"
              />
              <span
                v-if="pin.sites.length > 1"
                class="absolute -top-1.5 -right-2 rounded-full bg-foam px-1 text-[10px] leading-4 font-semibold text-abyss"
                aria-hidden="true"
              >
                {{ pin.sites.length }}
              </span>
              <span
                class="pointer-events-none absolute top-full mt-1 rounded bg-abyss/90 px-1.5 py-0.5 text-[11px] whitespace-nowrap text-foam/90 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                :class="pin.lon > 0 ? 'right-0' : 'left-0'"
              >
                {{
                  pin.sites.length > 1
                    ? `${pin.sites.length} transects · ${formatLatLon(pin)}`
                    : `${pin.sites[0]!.name} · ${formatLatLon(pin)}`
                }}
              </span>
            </RouterLink>
          </li>
        </ul>
      </div>
    </section>

    <!-- Call to action -->
    <section class="px-4 pt-12 pb-24 sm:px-6">
      <div
        v-reveal
        class="relative mx-auto max-w-4xl overflow-hidden rounded-3xl border border-scanner/30 bg-gradient-to-br from-scanner/15 via-abyss to-abyss px-6 py-14 text-center sm:px-12"
      >
        <h2 class="text-3xl font-semibold text-balance sm:text-4xl">
          Already have transect footage on a hard drive?
        </h2>
        <p class="mx-auto mt-4 max-w-xl text-foam/70">
          Give it a second life as a 3D model the whole research community can explore. The tool is
          free for anyone who needs it: just request access.
        </p>
        <RouterLink
          to="/request-access"
          class="mt-8 inline-block rounded-full bg-scanner px-7 py-3 font-semibold text-abyss shadow-[0_0_30px_rgb(44_211_217/0.35)] transition hover:shadow-[0_0_45px_rgb(44_211_217/0.6)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foam"
        >
          Request access
        </RouterLink>
      </div>
    </section>

    <footer
      class="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 border-t border-foam/10 px-4 py-8 text-sm text-foam/50 sm:flex-row sm:px-6"
    >
      <span class="font-semibold text-scanner">ScannerRoom</span>
      <span>Explore the coast, one dive at a time.</span>
      <nav aria-label="Legal" class="flex gap-4">
        <RouterLink to="/legal#terms" class="hover:text-scanner">Terms</RouterLink>
        <RouterLink to="/legal#privacy" class="hover:text-scanner">Privacy</RouterLink>
        <RouterLink to="/legal#notice" class="hover:text-scanner">Legal notice</RouterLink>
      </nav>
    </footer>
  </div>
</template>

<style scoped>
.hero-in {
  animation: rise 900ms cubic-bezier(0.2, 0.7, 0.2, 1) both;
  animation-delay: var(--delay);
}

.reveal {
  opacity: 0;
  translate: 0 24px;
  transition:
    opacity 800ms ease,
    translate 800ms cubic-bezier(0.2, 0.7, 0.2, 1);
  transition-delay: var(--reveal-delay);
}
.reveal.revealed {
  opacity: 1;
  translate: 0 0;
}

/* The pipeline connector draws itself from left to right. */
.scan-line.reveal {
  translate: none;
  scale: 0 1;
  transform-origin: left;
  transition: scale 1400ms cubic-bezier(0.6, 0, 0.2, 1);
}
.scan-line.reveal.revealed {
  scale: 1 1;
}

.group:hover .card-sweep {
  animation: sweep 1100ms ease;
}

.atlas-ocean {
  background: linear-gradient(180deg, rgb(44 211 217 / 0.55), rgb(44 211 217 / 0.25));
  mask: url('/geo/bathymetry.png') center / 100% 100% luminance;
}

/* A scanner line crossing the map, like the beam in the hero. */
.atlas-sweep {
  box-shadow: 0 0 16px 2px rgb(44 211 217 / 0.5);
  animation: cross 7s linear infinite;
}

@keyframes rise {
  from {
    opacity: 0;
    translate: 0 28px;
  }
}
@keyframes sweep {
  to {
    translate: 300% 0;
  }
}
/* Animated scanner-cyan border around the live reconstruction. */
.showcase-frame {
  background: conic-gradient(
    from var(--frame-angle),
    rgb(44 211 217 / 0.15),
    rgb(44 211 217 / 0.9),
    rgb(242 247 247 / 0.4),
    rgb(44 211 217 / 0.15) 40%
  );
  box-shadow: 0 30px 80px -30px rgb(44 211 217 / 0.35);
  animation: frame-spin 8s linear infinite;
}

@property --frame-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

@keyframes frame-spin {
  to {
    --frame-angle: 360deg;
  }
}

@keyframes cross {
  from {
    left: 0;
  }
  to {
    left: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .atlas-sweep {
    display: none;
  }
  .showcase-frame {
    animation: none;
  }
  .hero-in,
  .group:hover .card-sweep {
    animation: none;
  }
  .reveal,
  .scan-line.reveal {
    opacity: 1;
    translate: none;
    scale: 1 1;
    transition: none;
  }
}
</style>
