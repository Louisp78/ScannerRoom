<script setup lang="ts">
import TransectViewer from '@/components/TransectViewer.vue'

defineProps<{
  /** Transect key, i.e. the folder name under public/transects/. */
  transectKey: string
}>()
</script>

<template>
  <div class="flex h-screen flex-col">
    <header class="flex items-center gap-4 px-4 py-3">
      <RouterLink to="/" class="font-semibold text-scanner">ScannerRoom</RouterLink>
      <h1 class="truncate text-sm text-foam/80">{{ transectKey }}</h1>
    </header>
    <main class="min-h-0 flex-1">
      <!-- Keyed so that switching transects rebuilds the whole scene. -->
      <TransectViewer :key="transectKey" :base-url="`/transects/${transectKey}`" />
    </main>
  </div>
</template>
