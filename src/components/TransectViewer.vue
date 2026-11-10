<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue'
import { formatLatLon, type Site } from '@/sites'
import { formatTime, TransectScene } from '@/viewer/transectScene'

const props = defineProps<{
  /** Folder under public/ holding cloud.ply and path.json. */
  baseUrl: string
  /** Map entry of the transect, shown as a name + coordinates badge when known. */
  site?: Site
  /** Shown inside a scrolling page: see TransectScene's `embedded` option. */
  embedded?: boolean
}>()

const host = useTemplateRef<HTMLDivElement>('host')
const video = useTemplateRef<HTMLVideoElement>('video')
const videoUrl = ref<string>()
/** The video could not be loaded: playback falls back to the wall clock. */
const videoFailed = ref(false)
const progress = ref(0)
const error = ref<string>()
const range = ref<[number, number]>()
const time = ref(0)
/**
 * stopped: free orbit view. playing / paused: camera on the diver path,
 * time advancing in real video time or frozen.
 */
const playback = ref<'stopped' | 'playing' | 'paused'>('stopped')

let scene: TransectScene | undefined
let frameRequest = 0
let lastTick = 0

onMounted(async () => {
  scene = new TransectScene(host.value!, { embedded: props.embedded })
  try {
    const loaded = await scene.load(props.baseUrl, (r) => (progress.value = r))
    range.value = loaded.range
    videoUrl.value = loaded.videoUrl
    time.value = range.value[0]
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
})

/** The video thumbnail, when it can be used as the playback clock. */
function activeVideo(): HTMLVideoElement | undefined {
  return videoFailed.value ? undefined : (video.value ?? undefined)
}

watch(time, (t) => {
  scene?.setTime(t)
  // Slider moves: seek the video. While playing, time is read from the video
  // itself, so this never fires a seek of its own.
  const v = activeVideo()
  if (v && Math.abs(v.currentTime - t) > 0.25) v.currentTime = t
})
watch(playback, (state) => {
  scene?.setFollow(state !== 'stopped')
  const v = activeVideo()
  if (!v) return
  if (state === 'playing') v.play().catch(() => (videoFailed.value = true))
  else v.pause()
})

function tick(now: number) {
  const end = range.value![1]
  // The video is the clock: if it stalls to buffer, the camera waits for it.
  const v = activeVideo()
  const next = v ? v.currentTime : time.value + (now - lastTick) / 1000
  time.value = Math.min(next, end)
  lastTick = now
  if (time.value >= end) playback.value = 'paused'
  else frameRequest = requestAnimationFrame(tick)
}

function play() {
  if (!range.value) return
  // Replaying from the end starts the dive over.
  if (time.value >= range.value[1]) time.value = range.value[0]
  playback.value = 'playing'
  lastTick = performance.now()
  frameRequest = requestAnimationFrame(tick)
}

function pause() {
  cancelAnimationFrame(frameRequest)
  playback.value = 'paused'
}

function stop() {
  cancelAnimationFrame(frameRequest)
  playback.value = 'stopped'
  time.value = range.value?.[0] ?? 0
}

onBeforeUnmount(() => {
  cancelAnimationFrame(frameRequest)
  scene?.dispose()
})
</script>

<template>
  <div class="relative h-full w-full overflow-hidden">
    <div ref="host" class="absolute inset-0" />

    <!-- Top-left cluster: page-provided actions (e.g. back to the atlas), then the site badge. -->
    <div class="absolute top-4 left-4 flex max-w-[calc(100%-2rem)] items-stretch gap-2">
      <slot name="actions" />
      <div
        v-if="site"
        class="pointer-events-none flex min-w-0 flex-col justify-center gap-1 rounded-xl border border-foam/10 bg-abyss/70 px-3 py-2 backdrop-blur"
      >
        <span class="truncate text-sm font-semibold">{{ site.name }}</span>
        <span class="font-mono text-[11px] text-scanner">{{ formatLatLon(site) }}</span>
      </div>
    </div>

    <p v-if="error" class="absolute inset-x-0 top-1/2 text-center text-foam" role="alert">
      Could not load the transect: {{ error }}
    </p>
    <p v-else-if="!range" class="absolute inset-x-0 top-1/2 text-center text-scanner">
      Loading point cloud… {{ Math.round(progress * 100) }}%
    </p>

    <!-- Source video, in sync with the camera while traveling along the path. -->
    <video
      v-if="videoUrl && !videoFailed"
      v-show="playback !== 'stopped'"
      ref="video"
      :src="videoUrl"
      muted
      playsinline
      preload="auto"
      aria-label="Transect video"
      class="absolute top-4 right-4 w-48 rounded-lg border border-foam/20 shadow-lg sm:w-72"
      @error="videoFailed = true"
    />

    <div
      v-if="range"
      class="absolute inset-x-4 bottom-4 flex items-center gap-3 rounded-lg bg-abyss/80 px-4 py-3 text-sm text-foam backdrop-blur sm:inset-x-auto sm:left-1/2 sm:w-[36rem] sm:-translate-x-1/2"
    >
      <button
        v-if="playback !== 'playing'"
        type="button"
        class="grid size-8 shrink-0 place-items-center rounded-full bg-scanner text-abyss hover:bg-foam"
        aria-label="Play: follow the diver"
        @click="play"
      >
        <svg viewBox="0 0 16 16" class="ml-0.5 size-3.5" fill="currentColor" aria-hidden="true">
          <path d="M3 1.5v13l11-6.5z" />
        </svg>
      </button>
      <button
        v-else
        type="button"
        class="grid size-8 shrink-0 place-items-center rounded-full bg-scanner text-abyss hover:bg-foam"
        aria-label="Pause"
        @click="pause"
      >
        <svg viewBox="0 0 16 16" class="size-3.5" fill="currentColor" aria-hidden="true">
          <path d="M3 1.5h3.5v13H3zM9.5 1.5H13v13H9.5z" />
        </svg>
      </button>
      <button
        type="button"
        class="grid size-8 shrink-0 place-items-center rounded-full border border-foam/40 hover:border-scanner hover:text-scanner disabled:opacity-40"
        aria-label="Stop: back to the overview"
        :disabled="playback === 'stopped'"
        @click="stop"
      >
        <svg viewBox="0 0 16 16" class="size-3" fill="currentColor" aria-hidden="true">
          <rect x="2" y="2" width="12" height="12" rx="1" />
        </svg>
      </button>

      <label class="flex flex-1 items-center gap-3">
        <span class="sr-only">Video time</span>
        <span class="w-10 tabular-nums">{{ formatTime(time) }}</span>
        <input
          v-model.number="time"
          type="range"
          :min="range[0]"
          :max="range[1]"
          step="0.1"
          class="flex-1 accent-scanner"
        />
        <span class="w-10 text-right tabular-nums text-foam/60">{{ formatTime(range[1]) }}</span>
      </label>
    </div>
  </div>
</template>
