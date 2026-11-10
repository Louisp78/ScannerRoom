<script setup lang="ts">
import { computed } from 'vue'
import TransectViewer from '@/components/TransectViewer.vue'
import { SITES } from '@/sites'

const props = defineProps<{
  /** Transect key, i.e. the folder name under public/transects/. */
  transectKey: string
}>()

/** Undefined for a transect that is not on the map yet: the viewer then shows no badge. */
const site = computed(() => SITES.find((s) => s.transectKey === props.transectKey))
</script>

<template>
  <main class="h-svh">
    <h1 class="sr-only">{{ site?.name ?? transectKey }}</h1>
    <!-- Keyed so that switching transects rebuilds the whole scene. -->
    <TransectViewer :key="transectKey" :base-url="`/transects/${transectKey}`" :site="site">
      <template #actions>
        <RouterLink
          to="/explore"
          aria-label="Back to the atlas"
          class="group flex shrink-0 items-center gap-2 rounded-xl border border-foam/10 bg-abyss/70 px-3 text-sm font-semibold text-scanner backdrop-blur transition-colors hover:border-scanner/50 hover:bg-scanner/10 focus-visible:outline-2 focus-visible:outline-scanner"
        >
          <svg
            viewBox="0 0 16 16"
            class="size-4 transition-transform group-hover:-translate-x-0.5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M10 3 5 8l5 5" />
          </svg>
          <span class="hidden sm:inline">Atlas</span>
        </RouterLink>
      </template>
    </TransectViewer>
  </main>
</template>
