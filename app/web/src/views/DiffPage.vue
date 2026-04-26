<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useDiffStore } from '../stores/diff'
import DiffView from '../components/DiffView.vue'
import type { DiffMode } from '../types/diff'

const store = useDiffStore()
const mode = ref<DiffMode>('unified')

onMounted(() => {
  void store.load()
})
</script>

<template>
  <section class="diff-page">
    <div class="toolbar padding">
      <div class="tabs">
        <a :class="{ active: mode === 'unified' }" @click="mode = 'unified'">Unified</a>
        <a :class="{ active: mode === 'split' }" @click="mode = 'split'">Split</a>
      </div>
      <button class="border" @click="store.load()" :disabled="store.loading">
        <i>refresh</i>
        <span>Reload</span>
      </button>
    </div>

    <div v-if="store.loading" class="center-align padding">
      <progress class="circle"></progress>
    </div>

    <article v-else-if="store.error" class="error padding">
      <i>error</i>
      <span>{{ store.error }}</span>
    </article>

    <DiffView
      v-else
      :unified-diff="store.unifiedDiff"
      :left-filename="store.leftFilename"
      :right-filename="store.rightFilename"
      :mode="mode"
    />
  </section>
</template>

<style scoped>
.diff-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
</style>
