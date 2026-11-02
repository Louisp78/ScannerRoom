<script setup lang="ts">
import WorldGlobe from '@/components/WorldGlobe.vue'
</script>

<template>
  <div class="flex h-screen flex-col">
    <header class="px-4 py-3">
      <h1 class="font-semibold text-scanner">ScannerRoom</h1>
      <p class="text-sm text-foam/80">Explore the coast, one dive at a time.</p>
    </header>
    <main class="min-h-0 flex-1">
      <WorldGlobe />
    </main>
  </div>
</template>
