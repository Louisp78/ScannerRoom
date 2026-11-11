<script setup lang="ts">
// Signed-in user's profile: identity, number of contributions and their list (US-4.1).
import { onMounted, ref } from 'vue'
import AccountMenu from '@/components/AccountMenu.vue'
import { getMe, getMyTransects, type OwnTransect, type SessionUser } from '@/api'
import { formatLatLon, SITES } from '@/sites'

const user = ref<SessionUser>()
const contributions = ref<OwnTransect[]>()
const loadError = ref(false)

const siteByKey = new Map(SITES.map((site) => [site.transectKey, site]))
const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })

onMounted(async () => {
  try {
    ;[user.value, contributions.value] = await Promise.all([getMe(), getMyTransects()])
  } catch {
    loadError.value = true
  }
})
</script>

<template>
  <div class="relative isolate min-h-svh px-4 py-6 sm:py-10">
    <div
      class="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_50%_0%,rgb(44_211_217/0.16),transparent_60%)]"
      aria-hidden="true"
    />
    <header class="mx-auto flex max-w-3xl items-center justify-between gap-3">
      <RouterLink
        to="/explore"
        class="inline-flex items-center gap-2 font-semibold tracking-wide text-scanner focus-visible:outline-2 focus-visible:outline-scanner"
      >
        <span class="size-2.5 rounded-full bg-scanner shadow-[0_0_8px_var(--color-scanner)]" />
        ScannerRoom
      </RouterLink>
      <AccountMenu />
    </header>

    <main class="mx-auto mt-10 max-w-3xl">
      <p v-if="loadError" class="text-sm text-foam/70" role="alert">
        Could not load your profile. Try again in a moment.
      </p>
      <p v-else-if="!user || !contributions" class="text-sm text-foam/50">Loading…</p>
      <template v-else>
        <section class="flex flex-wrap items-end justify-between gap-6">
          <div class="min-w-0">
            <h1 class="truncate text-3xl font-semibold">{{ user.displayName }}</h1>
            <p v-if="user.orcidId" class="mt-2 text-sm text-foam/60">
              ORCID
              <a
                :href="`https://orcid.org/${user.orcidId}`"
                target="_blank"
                rel="noopener"
                class="font-mono text-scanner hover:underline"
              >
                {{ user.orcidId }}
              </a>
            </p>
          </div>
          <div class="rounded-2xl border border-scanner/30 px-5 py-3 text-right">
            <p class="font-mono text-3xl text-scanner">{{ contributions.length }}</p>
            <p class="text-xs tracking-wider text-foam/60 uppercase">
              {{ contributions.length === 1 ? 'contribution' : 'contributions' }}
            </p>
          </div>
        </section>

        <section class="mt-10">
          <h2 class="text-lg font-semibold">My transects</h2>
          <p v-if="!contributions.length" class="mt-4 text-sm text-foam/60">
            No transect is credited to you yet.
          </p>
          <ul v-else class="mt-4 space-y-3">
            <li v-for="transect in contributions" :key="transect.key">
              <RouterLink
                :to="{ name: 'transect', params: { transectKey: transect.key } }"
                class="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-2xl border border-foam/10 bg-abyss/60 px-4 py-3 transition-colors hover:border-scanner/50 hover:bg-scanner/5 focus-visible:outline-2 focus-visible:outline-scanner"
              >
                <span class="min-w-0">
                  <span class="block truncate font-semibold">
                    {{ siteByKey.get(transect.key)?.name ?? transect.key }}
                  </span>
                  <span
                    v-if="siteByKey.get(transect.key)"
                    class="block font-mono text-xs text-foam/50"
                  >
                    {{ formatLatLon(siteByKey.get(transect.key)!) }}
                  </span>
                </span>
                <span class="flex items-center gap-2 text-xs text-foam/60">
                  <span
                    v-if="transect.showcase"
                    class="rounded bg-scanner/20 px-1.5 py-0.5 text-scanner uppercase"
                  >
                    public
                  </span>
                  Added {{ dateFormat.format(new Date(transect.createdAt)) }}
                </span>
              </RouterLink>
            </li>
          </ul>
        </section>
      </template>
    </main>
  </div>
</template>
