import { ref } from 'vue';

export interface Municipality {
  name: string;
  folder: string;
}

export function useMunicipalities() {
  const municipalities = ref<Municipality[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const fetchMunicipalities = async () => {
    loading.value = true;
    error.value = null;
    try {
      // Fetch from the proxy
      const response = await fetch('/api/municipalities');
      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.statusText}`);
      }
      const data = await response.json();
      municipalities.value = data;
    } catch (err: any) {
      error.value = err.message || 'An error occurred while fetching municipalities.';
    } finally {
      loading.value = false;
    }
  };

  return {
    municipalities,
    loading,
    error,
    fetchMunicipalities
  };
}
