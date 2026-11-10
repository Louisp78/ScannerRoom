<script setup lang="ts">
import WorldGlobe from '@/components/WorldGlobe.vue'

const isDev = import.meta.env.DEV
</script>

<template>
  <div class="flex h-screen flex-col">
    <header class="flex items-start justify-between gap-4 px-4 py-3">
      <div>
        <h1 class="font-semibold text-scanner">ScannerRoom</h1>
        <p class="text-sm text-foam/80">Explore the coast, one dive at a time.</p>
      </div>
      <RouterLink v-if="isDev" to="/ingest" class="text-sm text-scanner underline">
        Add a transect
      </RouterLink>
    </header>
    <main class="min-h-0 flex-1">
      <WorldGlobe />
    </main>
  </div>
</template>
