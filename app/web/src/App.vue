<script setup lang="ts">
</script>

<template>
  <div class="app-shell">
    <header class="primary-container fixed">
      <nav>
        <h6 class="max">Diff Viewer</h6>
      </nav>
    </header>
    <main class="responsive">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
main {
  flex: 1;
  padding-top: 4rem;
  display: flex;
  flex-direction: column;
}
</style>
