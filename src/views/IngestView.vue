<script setup lang="ts">
// Dev-only page (see router): uploads a transect video to the local ingest
// endpoint and follows the reconstruction until the site lands on the map.
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  useTemplateRef,
  watch,
} from 'vue'
import { INGEST_ROUTE, type IngestJob, type IngestStep } from '@/ingestJob'

const STEPS: { step: IngestStep; label: string }[] = [
  { step: 'upload', label: 'Uploading the video' },
  { step: 'extract', label: 'Extracting frames' },
  { step: 'reconstruct', label: '3D reconstruction (LingBot-Map)' },
  { step: 'export', label: 'Web export' },
  { step: 'register', label: 'Adding to the map' },
]

const form = reactive({ name: '', key: '', lat: '', lon: '', fps: '2', start: '0', duration: '60' })
const file = ref<File>()
const keyEdited = ref(false)
const job = ref<IngestJob | null>(null)
const error = ref<string>()
const sending = ref(false)

let poll: ReturnType<typeof setInterval> | undefined

// Keep the log scrolled to its latest line, like a terminal.
const logEl = useTemplateRef<HTMLPreElement>('logEl')
watch(
  () => job.value?.log.at(-1),
  async () => {
    await nextTick()
    if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight
  },
)

const running = computed(() => sending.value || job.value?.status === 'running')
const currentIndex = computed(() => STEPS.findIndex((s) => s.step === job.value?.step))

/** Derives a folder-safe key from the name until the user edits it. */
function onNameInput() {
  if (keyEdited.value) return
  form.key = form.name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
}

/** Reconstruction speed measured on an M3 Pro (see playground/README.md). */
const SECONDS_PER_FRAME = 2

/** Length of the chosen video in seconds, read from its metadata. */
const videoDuration = ref<number>()

function onFileChange(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0]
  videoDuration.value = undefined
  if (!file.value) return
  const probe = document.createElement('video')
  const url = URL.createObjectURL(file.value)
  probe.preload = 'metadata'
  probe.onloadedmetadata = () => {
    videoDuration.value = Number.isFinite(probe.duration) ? probe.duration : undefined
    URL.revokeObjectURL(url)
  }
  probe.onerror = () => URL.revokeObjectURL(url)
  probe.src = url
}

/** Frames ffmpeg will extract: the window is clipped to the end of the video. */
const frameCount = computed(() => {
  const fps = Number(form.fps)
  const start = Number(form.start)
  let seconds = Number(form.duration)
  if (videoDuration.value !== undefined) seconds = Math.min(seconds, videoDuration.value - start)
  return fps > 0 && seconds > 0 ? Math.floor(fps * seconds) : 0
})

const estimate = computed(() => {
  const seconds = frameCount.value * SECONDS_PER_FRAME
  if (seconds < 60) return 'under a minute'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')}`
})

async function refresh() {
  const res = await fetch(INGEST_ROUTE)
  job.value = await res.json()
  if (job.value?.status !== 'running') stopPolling()
}

function startPolling() {
  stopPolling()
  poll = setInterval(() => refresh().catch(() => {}), 2000)
}

function stopPolling() {
  if (poll) clearInterval(poll)
  poll = undefined
}

async function submit() {
  if (!file.value) return
  error.value = undefined
  sending.value = true
  job.value = { key: form.key, name: form.name, status: 'running', step: 'upload', log: [] }
  try {
    const query = new URLSearchParams(form)
    const res = await fetch(`${INGEST_ROUTE}?${query}`, { method: 'POST', body: file.value })
    const body = await res.json()
    if (!res.ok && 'error' in body && !('status' in body)) {
      job.value = null
      error.value = body.error
      return
    }
    job.value = body
    if (body.status === 'running') startPolling()
  } catch (e) {
    job.value = null
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    sending.value = false
  }
}

onMounted(async () => {
  // Resume following a job started before a reload.
  await refresh().catch(() => {})
  if (job.value?.status === 'running') startPolling()
})
onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <header class="flex items-center gap-4 px-4 py-3">
      <RouterLink to="/" class="font-semibold text-scanner">ScannerRoom</RouterLink>
      <h1 class="text-sm text-foam/80">Add a transect (local)</h1>
    </header>

    <main class="mx-auto grid w-full max-w-5xl gap-8 px-4 pb-8 md:grid-cols-2">
      <form class="flex flex-col gap-4" @submit.prevent="submit">
        <p class="text-sm text-foam/70">
          The reconstruction runs on this Mac (MLX). Once done, the site shows up on the local map;
          commit <code>public/transects/&lt;key&gt;/</code> and <code>src/sites.json</code> to
          publish it.
        </p>

        <label class="flex flex-col gap-1 text-sm">
          Transect video
          <input
            type="file"
            accept="video/*"
            required
            :disabled="running"
            class="text-foam/80 file:mr-3 file:rounded file:border-0 file:bg-scanner file:px-3 file:py-1.5 file:font-medium file:text-abyss"
            @change="onFileChange"
          />
        </label>

        <label class="flex flex-col gap-1 text-sm">
          Site name
          <input
            v-model="form.name"
            required
            maxlength="120"
            :disabled="running"
            class="field"
            @input="onNameInput"
          />
        </label>

        <label class="flex flex-col gap-1 text-sm">
          Key (folder name)
          <input
            v-model="form.key"
            required
            maxlength="64"
            pattern="[a-z0-9]+(-[a-z0-9]+)*"
            title="Lowercase letters, digits and dashes, e.g. site4-transect1"
            :disabled="running"
            class="field font-mono"
            @input="keyEdited = true"
          />
        </label>

        <div class="grid grid-cols-2 gap-4">
          <label class="flex flex-col gap-1 text-sm">
            Latitude
            <input
              v-model="form.lat"
              type="number"
              step="any"
              min="-90"
              max="90"
              required
              :disabled="running"
              class="field"
            />
          </label>
          <label class="flex flex-col gap-1 text-sm">
            Longitude
            <input
              v-model="form.lon"
              type="number"
              step="any"
              min="-180"
              max="180"
              required
              :disabled="running"
              class="field"
            />
          </label>
        </div>

        <fieldset class="grid grid-cols-3 gap-4" :disabled="running">
          <legend class="mb-1 text-sm text-foam/70">Video excerpt to reconstruct</legend>
          <label class="flex flex-col gap-1 text-sm">
            Frames/s
            <input
              v-model="form.fps"
              type="number"
              step="any"
              min="0.1"
              max="10"
              required
              class="field"
            />
          </label>
          <label class="flex flex-col gap-1 text-sm">
            Start (s)
            <input v-model="form.start" type="number" step="any" min="0" required class="field" />
          </label>
          <label class="flex flex-col gap-1 text-sm">
            Duration (s)
            <input
              v-model="form.duration"
              type="number"
              step="any"
              min="1"
              required
              class="field"
            />
          </label>
        </fieldset>
        <p class="text-xs text-foam/60">
          {{ frameCount }} frames → about <strong class="text-foam">{{ estimate }}</strong> of
          reconstruction ({{ SECONDS_PER_FRAME }} s per frame on an M3 Pro).
          <template v-if="videoDuration !== undefined">
            Video length: {{ Math.floor(videoDuration / 60) }} min
            {{ String(Math.round(videoDuration % 60)).padStart(2, '0') }} s.
          </template>
        </p>

        <button
          type="submit"
          :disabled="running || !file"
          class="rounded bg-scanner px-4 py-2 font-medium text-abyss disabled:opacity-50"
        >
          Start the reconstruction
        </button>
        <p v-if="error" role="alert" class="text-sm text-red-300">{{ error }}</p>
      </form>

      <section v-if="job" class="flex min-w-0 flex-col gap-4" aria-live="polite">
        <h2 class="font-semibold">
          {{ job.name }} <span class="font-mono text-sm text-foam/60">{{ job.key }}</span>
        </h2>
        <ol class="flex flex-col gap-2 text-sm">
          <li v-for="(s, i) in STEPS" :key="s.step" class="flex items-center gap-2">
            <span
              class="size-2.5 rounded-full"
              :class="
                i < currentIndex || job.status === 'done'
                  ? 'bg-scanner'
                  : i === currentIndex && job.status === 'failed'
                    ? 'bg-red-400'
                    : i === currentIndex
                      ? 'animate-pulse bg-scanner/60'
                      : 'bg-foam/20'
              "
            />
            {{ s.label }}
          </li>
        </ol>

        <p v-if="job.status === 'done'" class="text-sm">
          Done.
          <RouterLink
            :to="{ name: 'transect', params: { transectKey: job.key } }"
            class="text-scanner underline"
          >
            Open the transect
          </RouterLink>
          or
          <RouterLink to="/" class="text-scanner underline">view the map</RouterLink>.
        </p>
        <p v-if="job.status === 'failed'" role="alert" class="text-sm text-red-300">
          Failed: {{ job.error }}
        </p>

        <pre
          v-if="job.log.length"
          ref="logEl"
          class="max-h-96 overflow-auto rounded bg-black/30 p-3 text-xs whitespace-pre-wrap text-foam/80"
          >{{ job.log.join('\n') }}</pre>
      </section>
    </main>
  </div>
</template>

<style scoped>
@reference '@/assets/main.css';

.field {
  @apply rounded border border-foam/20 bg-black/20 px-3 py-1.5 text-foam disabled:opacity-50;
}
</style>
