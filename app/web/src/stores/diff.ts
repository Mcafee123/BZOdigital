import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../composables/useApi'
import type { DiffPayload } from '../types/diff'

export const useDiffStore = defineStore('diff', () => {
  const unifiedDiff = ref('')
  const leftFilename = ref('')
  const rightFilename = ref('')
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function load() {
    loading.value = true
    error.value = null
    try {
      const data = await api<DiffPayload>('/api/diff')
      unifiedDiff.value = data.unified_diff
      leftFilename.value = data.left_filename
      rightFilename.value = data.right_filename
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return { unifiedDiff, leftFilename, rightFilename, loading, error, load }
})
