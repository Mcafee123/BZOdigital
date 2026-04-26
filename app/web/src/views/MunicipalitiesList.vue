<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useMunicipalities } from '../composables/useMunicipalities';

const router = useRouter();
const { municipalities, loading, error, fetchMunicipalities } = useMunicipalities();

const searchQuery = ref('');
const isDropdownOpen = ref(false);

const filteredMunicipalities = computed(() => {
  if (!searchQuery.value) return municipalities.value;
  const q = searchQuery.value.toLowerCase();
  return municipalities.value.filter(m => m.name.toLowerCase().includes(q));
});

const selectMunicipality = (folder: string) => {
  searchQuery.value = '';
  isDropdownOpen.value = false;
  router.push({ name: 'details', params: { folder } });
};

onMounted(() => {
  fetchMunicipalities();
});
</script>

<template>
  <div id="view-home" class="view active">
    <div class="logo">NUPLA</div>
    <div class="subtitle">Nutzungsplanungen einfach verstehen</div>
    
    <div class="search-wrapper" @focusout="setTimeout(() => isDropdownOpen = false, 200)">
      <input 
        type="text" 
        v-model="searchQuery"
        @focus="isDropdownOpen = true"
        placeholder="Gemeinde suchen (z.B. Bern)..." 
        autocomplete="off" 
      />
      
      <div v-if="isDropdownOpen && !loading" class="dropdown">
        <div v-if="filteredMunicipalities.length === 0" class="dropdown-item empty">
          Keine Gemeinde gefunden
        </div>
        <div 
          v-else
          v-for="muni in filteredMunicipalities" 
          :key="muni.folder"
          class="dropdown-item"
          @click.prevent="selectMunicipality(muni.folder)"
        >
          {{ muni.name }}
        </div>
      </div>
      
      <div class="search-hint">Tippen Sie einen Namen oder wählen Sie aus der Liste</div>
      <div v-if="error" style="color: red; margin-top: 10px;">{{ error }}</div>
    </div>
  </div>
</template>

<style scoped>
.dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 8px;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  max-height: 300px;
  overflow-y: auto;
  z-index: 10;
  text-align: left;
}

.dropdown-item {
  padding: 12px 20px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
  font-size: 16px;
  transition: background 0.2s;
}

.dropdown-item:last-child {
  border-bottom: none;
}

.dropdown-item:hover {
  background: #f8fafc;
  color: var(--accent-color);
}

.dropdown-item.empty {
  color: var(--text-muted);
  cursor: default;
}
.dropdown-item.empty:hover {
  background: transparent;
  color: var(--text-muted);
}
</style>
