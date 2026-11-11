<script setup lang="ts">
// Sign-in page (US-4.1): hands the browser over to ORCID or Google through the
// API, which brings it back to `redirect` once signed in.
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getProviders, signInUrl, type Provider } from '@/api'

const route = useRoute()

/** Same-site paths only; the API applies the same rule. */
const returnTo = computed(() => {
  const r = route.query.redirect
  return typeof r === 'string' && /^\/(?![/\\])/.test(r) ? r : '/explore'
})

const ERRORS: Record<string, string> = {
  cancelled: 'Sign-in was cancelled or refused by the provider.',
  'linked-elsewhere': 'This login is already linked to another ScannerRoom account.',
}
const errorMessage = computed(() => {
  const e = route.query.error
  return typeof e === 'string' ? (ERRORS[e] ?? 'Sign-in failed, please try again.') : undefined
})

const PROVIDERS: Record<Provider, { label: string; hint: string }> = {
  orcid: {
    label: 'Sign in with ORCID',
    hint: 'Recommended for researchers: your iD credits your transects.',
  },
  google: { label: 'Sign in with Google', hint: 'For everyone else.' },
}

const providers = ref<Provider[]>()
const loadError = ref(false)
onMounted(async () => {
  try {
    providers.value = await getProviders()
  } catch {
    loadError.value = true
  }
})
</script>

<template>
  <div class="relative isolate grid min-h-svh place-items-center px-4 py-16">
    <div
      class="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_50%_0%,rgb(44_211_217/0.16),transparent_60%)]"
      aria-hidden="true"
    />
    <main class="w-full max-w-md">
      <RouterLink
        to="/"
        class="mb-8 inline-flex items-center gap-2 font-semibold tracking-wide text-scanner focus-visible:outline-2 focus-visible:outline-scanner"
      >
        <span class="size-2.5 rounded-full bg-scanner shadow-[0_0_8px_var(--color-scanner)]" />
        ScannerRoom
      </RouterLink>

      <div
        class="rounded-3xl border border-foam/10 bg-abyss/90 p-6 shadow-[0_20px_80px_-30px_rgb(44_211_217/0.5)] sm:p-8"
      >
        <h1 class="text-2xl font-semibold">Sign in</h1>
        <p class="mt-2 text-sm text-foam/70">
          The atlas and the 3D transects are shared with signed-in members only.
        </p>

        <p
          v-if="errorMessage"
          class="mt-5 rounded-lg border border-red-400/40 bg-red-900/30 px-3 py-2 text-sm"
          role="alert"
        >
          {{ errorMessage }}
        </p>

        <ul v-if="providers?.length" class="mt-6 space-y-3">
          <li v-for="provider in providers" :key="provider">
            <a
              :href="signInUrl(provider, returnTo)"
              class="block rounded-2xl border border-scanner/40 px-4 py-3 transition-colors hover:bg-scanner/10 focus-visible:outline-2 focus-visible:outline-scanner"
            >
              <span class="font-semibold text-scanner">{{ PROVIDERS[provider].label }}</span>
              <span class="mt-0.5 block text-xs text-foam/60">{{ PROVIDERS[provider].hint }}</span>
            </a>
          </li>
        </ul>
        <p v-else-if="loadError || providers" class="mt-6 text-sm text-foam/70" role="alert">
          Sign-in is unavailable right now. Please come back later.
        </p>
        <p v-else class="mt-6 text-sm text-foam/50">Loading…</p>

        <p v-if="providers?.length" class="mt-4 text-xs text-foam/50">
          By signing in, you accept the
          <RouterLink to="/legal#terms" class="text-scanner hover:underline"
            >terms of use</RouterLink
          >
          and the
          <RouterLink to="/legal#privacy" class="text-scanner hover:underline"
            >privacy policy</RouterLink
          >.
        </p>

        <p class="mt-8 text-xs text-foam/50">
          No account yet? Signing in creates one. Want to add your own transects?
          <RouterLink to="/request-access" class="text-scanner underline-offset-2 hover:underline">
            Request access
          </RouterLink>
        </p>
      </div>
    </main>
  </div>
</template>
