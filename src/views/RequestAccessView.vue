<script setup lang="ts">
import { reactive, ref } from 'vue'

/** Inbox receiving access requests; the static site has no backend, so the form hands off to mailto. */
const CONTACT_EMAIL = 'lgup.official@gmail.com'

const form = reactive({
  name: '',
  email: '',
  organisation: '',
  footage: '',
  message: '',
})
const sent = ref(false)

const pillars = [
  {
    title: 'An individual initiative',
    text: 'ScannerRoom is built and maintained by one independent developer, not a company or a lab.',
  },
  {
    title: 'Free for whoever needs it',
    text: 'Researchers, NGOs, students, divers: if your work benefits from a 3D reef, you get access at no cost.',
  },
  {
    title: 'Real costs behind the scenes',
    text: 'GPU reconstruction, storage and hosting are paid out of pocket. Every request shows the project is worth keeping alive.',
  },
]

function submit() {
  const body = [
    `Name: ${form.name}`,
    `Email: ${form.email}`,
    `Organisation: ${form.organisation || '-'}`,
    `Footage to reconstruct: ${form.footage || '-'}`,
    '',
    form.message,
  ].join('\n')
  const subject = `ScannerRoom access request - ${form.name}`
  window.location.href = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
  sent.value = true
}
</script>

<template>
  <div class="relative isolate min-h-svh overflow-x-hidden">
    <div
      class="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_15%_0%,rgb(44_211_217/0.16),transparent_55%),radial-gradient(ellipse_at_100%_100%,rgb(44_211_217/0.08),transparent_50%)]"
      aria-hidden="true"
    />
    <div class="sonar absolute top-1/3 -left-40 -z-10 size-[36rem]" aria-hidden="true" />

    <header class="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
      <RouterLink
        to="/"
        class="flex items-center gap-2 font-semibold tracking-wide text-scanner focus-visible:outline-2 focus-visible:outline-scanner"
      >
        <span class="relative flex size-2.5">
          <span
            class="absolute inline-flex size-full animate-ping rounded-full bg-scanner opacity-60 motion-reduce:animate-none"
          />
          <span class="relative inline-flex size-2.5 rounded-full bg-scanner" />
        </span>
        ScannerRoom
      </RouterLink>
      <RouterLink
        to="/explore"
        class="rounded-full border border-scanner/40 px-4 py-1.5 text-sm text-scanner transition-colors hover:bg-scanner/10 focus-visible:outline-2 focus-visible:outline-scanner"
      >
        Back to the atlas
      </RouterLink>
    </header>

    <main
      class="mx-auto grid max-w-6xl gap-12 px-4 pt-[6vh] pb-24 sm:px-6 lg:grid-cols-[1fr_minmax(0,32rem)] lg:gap-16"
    >
      <section>
        <p
          class="rise mb-4 text-xs font-medium tracking-[0.25em] text-scanner uppercase"
          style="--delay: 0ms"
        >
          Add a transect
        </p>
        <h1
          class="rise max-w-xl text-4xl leading-tight font-semibold text-balance sm:text-5xl"
          style="--delay: 120ms"
        >
          Request access to the
          <span class="bg-gradient-to-r from-scanner to-foam bg-clip-text text-transparent">
            reconstruction tool.
          </span>
        </h1>
        <p class="rise mt-6 max-w-lg text-foam/75 sm:text-lg" style="--delay: 240ms">
          Uploads are opened by hand for now. Tell me a little about your footage and I will get
          back to you to turn it into a 3D seabed on the shared atlas.
        </p>

        <ul class="mt-10 space-y-4">
          <li
            v-for="(pillar, i) in pillars"
            :key="pillar.title"
            class="rise flex gap-4 rounded-2xl border border-foam/10 bg-foam/[0.03] p-5"
            :style="{ '--delay': `${360 + 120 * i}ms` }"
          >
            <span
              class="grid size-9 shrink-0 place-items-center rounded-full border border-scanner/50 font-mono text-xs text-scanner shadow-[0_0_16px_rgb(44_211_217/0.25)]"
            >
              {{ String(i + 1).padStart(2, '0') }}
            </span>
            <div>
              <h2 class="font-semibold">{{ pillar.title }}</h2>
              <p class="mt-1 text-sm leading-relaxed text-foam/70">{{ pillar.text }}</p>
            </div>
          </li>
        </ul>

        <p class="rise mt-6 max-w-lg text-sm text-foam/60" style="--delay: 720ms">
          Sending this form is free and commits you to nothing. It is also, quite simply, the best
          way to support the project.
        </p>
      </section>

      <section class="rise relative rounded-3xl p-px" style="--delay: 300ms">
        <div
          class="absolute inset-0 rounded-3xl bg-gradient-to-br from-scanner/60 via-scanner/10 to-foam/10"
          aria-hidden="true"
        />
        <div
          class="relative rounded-3xl bg-abyss/95 p-6 shadow-[0_20px_80px_-30px_rgb(44_211_217/0.5)] backdrop-blur sm:p-8"
        >
          <div v-if="sent" class="py-10 text-center" role="status">
            <span
              class="mx-auto grid size-14 place-items-center rounded-full border border-scanner/60 text-2xl text-scanner shadow-[0_0_30px_rgb(44_211_217/0.4)]"
              aria-hidden="true"
            >
              ✓
            </span>
            <h2 class="mt-6 text-2xl font-semibold">Almost there</h2>
            <p class="mx-auto mt-3 max-w-sm text-foam/70">
              Your mail app should have opened with the request ready. Just hit send. Nothing
              opened? Write directly to
              <a :href="`mailto:${CONTACT_EMAIL}`" class="text-scanner hover:underline">
                {{ CONTACT_EMAIL }}
              </a>
              .
            </p>
            <button
              type="button"
              class="mt-8 text-sm text-foam/60 underline-offset-4 hover:text-foam hover:underline focus-visible:outline-2 focus-visible:outline-scanner"
              @click="sent = false"
            >
              Edit my request
            </button>
          </div>

          <form v-else class="space-y-5" @submit.prevent="submit">
            <h2 class="text-xl font-semibold">Your request</h2>
            <div class="grid gap-5 sm:grid-cols-2">
              <label class="field">
                <span>Name</span>
                <input v-model.trim="form.name" required autocomplete="name" />
              </label>
              <label class="field">
                <span>Email</span>
                <input v-model.trim="form.email" type="email" required autocomplete="email" />
              </label>
            </div>
            <label class="field">
              <span>Organisation <em>optional</em></span>
              <input
                v-model.trim="form.organisation"
                autocomplete="organization"
                placeholder="Lab, NGO, dive club…"
              />
            </label>
            <label class="field">
              <span>Footage to reconstruct <em>optional</em></span>
              <input v-model.trim="form.footage" placeholder="e.g. 3 transects, ~10 min each" />
            </label>
            <label class="field">
              <span>What will you use it for?</span>
              <textarea
                v-model.trim="form.message"
                required
                rows="5"
                placeholder="Site, research question, how the 3D model would help…"
              />
            </label>
            <button
              type="submit"
              class="w-full rounded-full bg-scanner px-6 py-3 font-semibold text-abyss shadow-[0_0_30px_rgb(44_211_217/0.35)] transition hover:shadow-[0_0_45px_rgb(44_211_217/0.6)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foam"
            >
              Send my request
            </button>
            <p class="text-center text-xs text-foam/50">
              Opens your mail app with a prefilled email to {{ CONTACT_EMAIL }}.
            </p>
          </form>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.rise {
  animation: rise 900ms cubic-bezier(0.2, 0.7, 0.2, 1) both;
  animation-delay: var(--delay);
}

@keyframes rise {
  from {
    opacity: 0;
    translate: 0 20px;
  }
}

.sonar {
  border-radius: 9999px;
  background: repeating-radial-gradient(circle, rgb(44 211 217 / 0.07) 0 1px, transparent 1px 48px);
  mask-image: radial-gradient(circle, black, transparent 70%);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.875rem;
  color: rgb(242 247 247 / 0.8);
}

.field em {
  font-style: normal;
  font-size: 0.75rem;
  color: rgb(242 247 247 / 0.4);
}

.field input,
.field textarea {
  width: 100%;
  border-radius: 0.75rem;
  border: 1px solid rgb(242 247 247 / 0.12);
  background: rgb(242 247 247 / 0.04);
  padding: 0.7rem 0.9rem;
  color: var(--color-foam);
  transition:
    border-color 150ms,
    box-shadow 150ms;
}

.field textarea {
  resize: vertical;
}

.field input::placeholder,
.field textarea::placeholder {
  color: rgb(242 247 247 / 0.3);
}

.field input:focus,
.field textarea:focus {
  outline: none;
  border-color: var(--color-scanner);
  box-shadow: 0 0 0 3px rgb(44 211 217 / 0.2);
}

@media (prefers-reduced-motion: reduce) {
  .rise {
    animation: none;
  }
}
</style>
