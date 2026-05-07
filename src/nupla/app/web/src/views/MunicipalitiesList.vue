<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useMunicipalities } from '../composables/useMunicipalities';

const router = useRouter();
const { municipalities, loading, error, fetchMunicipalities } = useMunicipalities();

const searchQuery = ref('');
const isDropdownOpen = ref(false);

const isModalOpen = ref(false);
const pdfUrl = ref('/OLL2026_BZO_V06.pdf');

const handleKeydown = (e: KeyboardEvent) => {
  if (!isModalOpen.value) return;
  if (e.key === 'Escape') isModalOpen.value = false;
};

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

const handleFocusOut = () => {
  setTimeout(() => {
    isDropdownOpen.value = false;
  }, 200);
};

onMounted(() => {
  fetchMunicipalities();
  window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <div id="view-home" class="view active">
    <div class="logo">NUPLA</div>
    <div class="subtitle">Nutzungsplanungen einfach verstehen</div>
    
    <div class="search-wrapper" @focusout="handleFocusOut">
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

    <!-- Presentation Button -->
    <button class="presentation-btn" @click="isModalOpen = true">
      Präsentation
    </button>

    <!-- Presentation Modal -->
    <Teleport to="body">
      <div v-if="isModalOpen" class="modal-overlay" @click.self="isModalOpen = false">
        <button class="modal-close" @click="isModalOpen = false">✕</button>
        <div class="modal-content">
          <iframe 
            :src="pdfUrl + '#toolbar=0&navpanes=0&scrollbar=0'" 
            class="pdf-viewer"
            frameborder="0"
          ></iframe>
        </div>
      </div>
    </Teleport>

    <!-- Attribution -->
    <div class="attribution">
      <p>Entwickelt im Rahmen vom:</p>
      <a href="https://ejustice.ch/open-legal-lab/" target="_blank" rel="noopener noreferrer">
        <img src="/eJustice_logo.png" alt="Open Legal Lab eJustice Logo" class="ejustice-logo" />
      </a>
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

.presentation-btn {
  margin-top: 40px;
  padding: 10px 24px;
  font-size: 14px;
  font-weight: 500;
  color: var(--surface-color);
  background-color: #444952;
  border: 1px solid #444952;
  border-radius: var(--radius, 8px);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  transition: all 0.2s ease;
  letter-spacing: 0.5px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.presentation-btn:hover {
  background-color: #374151;
  border-color: #374151;
  transform: translateY(-1px);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.25);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 40px;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.modal-content {
  position: relative;
  width: 100%;
  max-width: 1200px;
  height: 100%;
  max-height: 800px;
  background: var(--surface-color, #fff);
  border-radius: 16px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-close {
  position: absolute;
  top: 24px;
  right: 24px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #4b5563;
  color: white;
  border: 2px solid white;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 10;
  transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.modal-close:hover {
  background: #374151;
  transform: scale(1.1);
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.4);
}

.pdf-viewer {
  width: 100%;
  height: 100%;
  flex: 1;
  border: none;
}

.attribution {
  margin-top: 60px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
}

.attribution a {
  display: flex;
  justify-content: center;
  align-items: center;
}

.attribution p {
  color: var(--text-muted);
  font-size: 14px;
  margin: 0;
  font-weight: 500;
}

.ejustice-logo {
  height: 48px;
  width: auto;
  opacity: 0.85;
  transition: all 0.2s ease;
  filter: grayscale(20%);
}

.ejustice-logo:hover {
  opacity: 1;
  filter: grayscale(0%);
  transform: scale(1.02);
}
</style>
