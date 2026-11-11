<script setup lang="ts">
// Admin control in the viewer badge: reassign the transect to another user (US-4.1).
import { ref } from 'vue'
import { getUsers, setContributor, type TransectDetails, type UserSummary } from '@/api'

const props = defineProps<{ transectKey: string; contributor: TransectDetails['contributor'] }>()
const emit = defineEmits<{ changed: [contributor: TransectDetails['contributor']] }>()

const users = ref<UserSummary[]>()
const editing = ref(false)
const saving = ref(false)
const error = ref<string>()

async function open() {
  error.value = undefined
  editing.value = true
  try {
    users.value ??= await getUsers()
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function onChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  saving.value = true
  error.value = undefined
  try {
    const details = await setContributor(props.transectKey, value ? Number(value) : null)
    emit('changed', details.contributor)
    editing.value = false
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <span class="pointer-events-auto flex flex-wrap items-center gap-1 text-[11px]">
    <button
      v-if="!editing"
      type="button"
      class="text-scanner hover:underline focus-visible:outline-2 focus-visible:outline-scanner"
      @click="open"
    >
      {{ contributor ? 'change contributor' : 'set contributor' }}
    </button>
    <template v-else>
      <label class="sr-only" for="contributor-picker">Contributor</label>
      <select
        id="contributor-picker"
        class="max-w-[14rem] rounded border border-foam/20 bg-abyss px-1 py-0.5 text-foam"
        :disabled="!users || saving"
        :value="contributor?.id ?? ''"
        @change="onChange"
      >
        <option value="">No contributor</option>
        <option v-for="user in users" :key="user.id" :value="user.id">
          {{ user.displayName }}{{ user.orcidId ? ` (${user.orcidId})` : '' }}
        </option>
      </select>
      <button
        type="button"
        class="text-foam/60 hover:text-foam"
        :disabled="saving"
        @click="editing = false"
      >
        cancel
      </button>
    </template>
    <span v-if="error" class="text-red-300" role="alert">{{ error }}</span>
  </span>
</template>
