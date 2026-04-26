<script setup lang="ts">
import { computed } from 'vue'
import { DiffView as GitDiffView, DiffModeEnum } from '@git-diff-view/vue'
import '@git-diff-view/vue/styles/diff-view.css'

const props = defineProps<{
  unifiedDiff: string
  leftFilename: string
  rightFilename: string
  mode: 'split' | 'unified'
  leftContent?: string
  rightContent?: string
}>()

const diffMode = computed(() =>
  props.mode === 'split' ? DiffModeEnum.Split : DiffModeEnum.Unified,
)

const diffData = computed(() => ({
  oldFile: {
    fileName: props.leftFilename,
    fileLang: 'markdown',
    content: props.leftContent ?? '',
  },
  newFile: {
    fileName: props.rightFilename,
    fileLang: 'markdown',
    content: props.rightContent ?? '',
  },
  hunks: [props.unifiedDiff],
}))

const isEmpty = computed(() => !props.unifiedDiff)
</script>

<template>
  <div class="diff-view-wrapper">
    <div v-if="isEmpty" class="center-align padding">
      <i class="extra">check_circle</i>
      <p>Documents are identical</p>
    </div>
    <GitDiffView
      v-else
      :data="diffData"
      :diff-view-mode="diffMode"
      :diff-view-wrap="true"
      :diff-view-highlight="true"
      :diff-view-add-widget="false"
    />
  </div>
</template>

<style scoped>
.diff-view-wrapper {
  flex: 1;
  overflow: auto;
  min-height: 0;
}
</style>
