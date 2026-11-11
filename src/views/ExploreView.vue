<script setup lang="ts">
import AccountMenu from '@/components/AccountMenu.vue'
import WorldGlobe from '@/components/WorldGlobe.vue'
import { SITES } from '@/sites'

// The upload tool only runs on the dev server; production visitors request access instead.
const addTransectRoute = import.meta.env.DEV ? '/ingest' : '/request-access'
</script>

<template>
  <div class="relative h-svh overflow-hidden">
    <main class="absolute inset-0">
      <h1 class="sr-only">ScannerRoom atlas</h1>
      <WorldGlobe />
    </main>

    <!-- Floating over the globe; the gaps around it keep the globe draggable. -->
    <header class="pointer-events-none absolute inset-x-0 top-0 p-3 sm:p-4">
      <div
        class="pointer-events-auto mx-auto flex max-w-6xl items-center justify-between gap-3 rounded-2xl border border-foam/10 bg-abyss/60 py-2 pr-2 pl-4 shadow-[0_10px_40px_-15px_rgb(44_211_217/0.35)] backdrop-blur-md"
      >
        <RouterLink
          to="/"
          class="group flex min-w-0 items-center gap-3 focus-visible:outline-2 focus-visible:outline-scanner"
        >
          <span class="relative flex size-2.5 shrink-0">
            <span
              class="absolute inline-flex size-full animate-ping rounded-full bg-scanner opacity-60 motion-reduce:animate-none"
            />
            <span class="relative inline-flex size-2.5 rounded-full bg-scanner" />
          </span>
          <span class="flex min-w-0 flex-col leading-tight">
            <span class="font-semibold tracking-wide text-scanner">ScannerRoom</span>
            <span class="hidden truncate text-xs text-foam/60 sm:block">
              Explore the coast, one dive at a time.
            </span>
          </span>
        </RouterLink>

        <div class="flex shrink-0 items-center gap-2">
          <span
            class="hidden items-center gap-2 rounded-full border border-scanner/30 px-3 py-1.5 font-mono text-xs text-scanner sm:flex"
          >
            <span class="size-1.5 rounded-full bg-scanner shadow-[0_0_8px_var(--color-scanner)]" />
            {{ SITES.length }} transects mapped
          </span>
          <RouterLink
            :to="addTransectRoute"
            class="rounded-full bg-scanner px-4 py-1.5 text-sm font-semibold text-abyss transition hover:shadow-[0_0_20px_rgb(44_211_217/0.6)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foam"
          >
            Add a transect
          </RouterLink>
          <AccountMenu />
        </div>
      </div>
    </header>

    <p
      class="pointer-events-none absolute inset-x-0 bottom-4 text-center text-xs tracking-wider text-foam/50 uppercase"
    >
      Drag to spin · scroll to zoom · pick a pin to dive in
    </p>
  </div>
</template>
