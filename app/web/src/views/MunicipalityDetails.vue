<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

const folderName = route.params.folder as string;

const loading = ref(true);
const error = ref<string | null>(null);
const municipality = ref({ name: '', status: '' });
const pdfs = ref<any[]>([]);

onMounted(async () => {
  try {
    const response = await fetch(`/api/municipalities/${folderName}/pdfs`);
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Municipality not found');
      }
      throw new Error(`Failed to fetch PDFs: ${response.statusText}`);
    }
    const data = await response.json();
    municipality.value = data.municipality;
    pdfs.value = data.pdfs;
  } catch (err: any) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div id="view-municipality" class="view active">
    <div class="container">
      
      <a class="back-btn" @click.prevent="router.push('/')">← Neue Suche</a>

      <div v-if="loading">Lädt...</div>
      
      <div v-else-if="error" style="color: red;">{{ error }}</div>
      
      <div v-else>
        <div class="header-section">
          <h1>
            <span>Gemeinde {{ municipality.name }}</span>
            <span class="status-badge">{{ municipality.status }}</span>
          </h1>
          
          <div class="documents-row" v-if="pdfs.length > 0">
            <a 
              v-for="pdf in pdfs" 
              :key="pdf.id"
              :href="pdf.url" 
              target="_blank"
              class="doc-card"
            >
              📄 {{ pdf.label }}
            </a>
          </div>
          <div v-else style="margin-top: 20px; color: var(--text-muted);">
            Keine Dokumente gefunden.
          </div>
        </div>
      </div>
      
    </div>
  </div>
</template>

<style scoped>
/* Inherits from style.css */
</style>
