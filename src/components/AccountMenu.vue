<script setup lang="ts">
// Signed-in user in the atlas header: name, ORCID linking, profile, sign-out (US-4.1).
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getMe, getProviders, signInUrl, signOut, type SessionUser } from '@/api'

const route = useRoute()
const router = useRouter()
const user = ref<SessionUser>()
/** ORCID is offered for linking when enabled and not linked yet: it credits the user's transects. */
const canLinkOrcid = ref(false)
const open = ref(false)

onMounted(async () => {
  user.value = await getMe()
  if (user.value && !user.value.orcidId)
    canLinkOrcid.value = (await getProviders()).includes('orcid')
})

async function onSignOut() {
  await signOut()
  await router.push('/')
}
</script>

<template>
  <div v-if="user" class="relative">
    <button
      type="button"
      class="flex max-w-[12rem] items-center gap-2 rounded-full border border-foam/20 px-3 py-1.5 text-sm hover:border-scanner/60 focus-visible:outline-2 focus-visible:outline-scanner"
      :aria-expanded="open"
      aria-haspopup="menu"
      @click="open = !open"
    >
      <span class="truncate">{{ user.displayName }}</span>
      <span
        v-if="user.isAdmin"
        class="rounded bg-scanner/20 px-1 text-[10px] text-scanner uppercase"
      >
        admin
      </span>
    </button>
    <div
      v-if="open"
      role="menu"
      class="absolute right-0 mt-2 w-60 rounded-2xl border border-foam/10 bg-abyss/95 p-2 text-sm shadow-xl backdrop-blur"
    >
      <p v-if="user.orcidId" class="px-3 py-2 text-xs text-foam/60">
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
      <a
        v-else-if="canLinkOrcid"
        role="menuitem"
        :href="signInUrl('orcid', route.fullPath, true)"
        class="block rounded-lg px-3 py-2 hover:bg-scanner/10"
      >
        Link my ORCID iD
        <span class="block text-xs text-foam/60"
          >Credits your transects to your researcher iD.</span
        >
      </a>
      <RouterLink
        role="menuitem"
        to="/profile"
        class="block rounded-lg px-3 py-2 hover:bg-scanner/10"
      >
        My profile
      </RouterLink>
      <button
        type="button"
        role="menuitem"
        class="block w-full rounded-lg px-3 py-2 text-left hover:bg-scanner/10"
        @click="onSignOut"
      >
        Sign out
      </button>
    </div>
  </div>
</template>
