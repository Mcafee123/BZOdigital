<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { marked } from 'marked';
import { api } from '../composables/useApi';
import type { CrossReferenceEntry, CrossReferencesPayload } from '../types/crossreferences';

marked.setOptions({ gfm: true, breaks: false });

const route = useRoute();
const router = useRouter();

const folderName = route.params.folder as string;

const loading = ref(true);
const error = ref<string | null>(null);
const data = ref<CrossReferencesPayload | null>(null);
const selected = ref<string>((route.query.art as string) || '');

const renderedBzo = computed<string>(() => {
  if (!data.value) return '';
  return marked.parse(data.value.bzo_markdown) as string;
});

const selectedRefs = computed<CrossReferenceEntry[]>(() => {
  if (!data.value || !selected.value) return [];
  return data.value.cross_references[selected.value] ?? [];
});

const selectedHasRefs = computed(() => selectedRefs.value.length > 0);

interface DocChip {
  key: string;
  label: string;
  count: number;
}

function docLabel(file: string, labels: string[]): string {
  if (labels.length > 0) return labels[0];
  return file.replace(/\.md$/i, '');
}

const docTotals = computed<DocChip[]>(() => {
  if (!data.value) return [];
  const totals = new Map<string, DocChip>();
  for (const entries of Object.values(data.value.cross_references)) {
    for (const e of entries) {
      const key = e.source_file;
      const existing = totals.get(key);
      if (existing) {
        existing.count += 1;
      } else {
        totals.set(key, { key, label: docLabel(e.source_file, e.source_labels), count: 1 });
      }
    }
  }
  return [...totals.values()].sort((a, b) => b.count - a.count);
});

function badgeClass(art: string) {
  const has = (data.value?.cross_references[art]?.length ?? 0) > 0;
  return {
    'art-badge': true,
    'is-selected': art === selected.value,
    'has-refs': has && art !== selected.value,
    'no-refs': !has && art !== selected.value,
  };
}

function selectArticle(art: string) {
  selected.value = art;
  router.replace({ query: { ...route.query, art } });
  nextTick(() => {
    const el = document.querySelector(`a[name="art-${art}"]`) as HTMLElement | null;
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
}

watch(() => route.query.art, (q) => {
  if (typeof q === 'string' && q !== selected.value) {
    selected.value = q;
  }
});

onMounted(async () => {
  try {
    data.value = await api<CrossReferencesPayload>(
      `/api/municipalities/${folderName}/crossreferences`,
    );
    if (!selected.value && data.value.articles.length > 0) {
      selected.value = data.value.articles[0];
    }
  } catch (err: any) {
    error.value = err.message || String(err);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="xref-view">
    <header class="xref-header">
      <div class="xref-title">
        <h1>BZO Querverweise</h1>
        <span v-if="data" class="xref-subtitle">
          {{ data.municipality }} — {{ data.bzo_filename }}
        </span>
      </div>
      <a class="back-btn" @click.prevent="router.push(`/details/${folderName}`)">Zurück</a>
    </header>

    <div v-if="loading" class="xref-loading">Lädt...</div>
    <div v-else-if="error" class="xref-error">{{ error }}</div>

    <div v-else-if="data" class="xref-grid">
      <article class="xref-doc markdown" v-html="renderedBzo"></article>

      <aside class="xref-side">
        <div class="xref-selected">
          <h2>Art. {{ selected || '—' }}</h2>
          <p class="xref-count">
            {{ selectedHasRefs
              ? `${selectedRefs.length} Querverweis${selectedRefs.length === 1 ? '' : 'e'}`
              : 'Keine Querverweise' }}
          </p>
        </div>

        <div class="xref-articles">
          <button
            v-for="art in data.articles"
            :key="art"
            type="button"
            :class="badgeClass(art)"
            @click="selectArticle(art)"
          >{{ art }}</button>
        </div>

        <div class="xref-docs">
          <h3>Dokumente</h3>
          <div class="xref-doc-chips">
            <span v-for="d in docTotals" :key="d.key" class="doc-chip">
              {{ d.label }} <span class="doc-chip-count">{{ d.count }}</span>
            </span>
          </div>
        </div>

        <div class="xref-refs">
          <p v-if="!selectedHasRefs" class="xref-empty">
            Dieser Artikel wird in keinem Begleitdokument referenziert.
          </p>
          <ul v-else class="xref-ref-list">
            <li v-for="(r, i) in selectedRefs" :key="i" class="xref-ref">
              <div class="xref-ref-head">
                <span class="xref-ref-doc">
                  {{ docLabel(r.source_file, r.source_labels) }}
                </span>
                <span class="xref-ref-cite">{{ r.citation_text }}</span>
              </div>
              <p class="xref-ref-paragraph">{{ r.paragraph }}</p>
            </li>
          </ul>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.xref-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-color);
}

.xref-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 28px;
  background: var(--surface-color);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.xref-title {
  display: flex;
  align-items: baseline;
  gap: 14px;
  min-width: 0;
}
.xref-title h1 {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.3px;
}
.xref-subtitle {
  font-size: 14px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.xref-header .back-btn {
  margin-bottom: 0;
  font-weight: 500;
  color: var(--accent-color);
}
.xref-header .back-btn:hover { color: var(--accent-hover); }

.xref-loading,
.xref-error {
  padding: 40px;
  color: var(--text-muted);
}
.xref-error { color: #b91c1c; }

.xref-grid {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(380px, 2fr);
  gap: 0;
  overflow: hidden;
}

.xref-doc {
  overflow-y: auto;
  padding: 28px 36px;
  background: var(--surface-color);
}

.xref-side {
  overflow-y: auto;
  padding: 24px 28px;
  border-left: 1px solid var(--border-color);
  background: var(--bg-color);
}

.xref-selected h2 {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
}
.xref-count {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 2px;
}

.xref-articles {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 16px;
}
.art-badge {
  min-width: 36px;
  height: 28px;
  padding: 0 10px;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  border-radius: 999px;
  cursor: pointer;
  border: 1px solid var(--border-color);
  background: var(--surface-color);
  color: var(--text-muted);
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.art-badge:hover { border-color: var(--accent-color); color: var(--accent-color); }
.art-badge.has-refs {
  background: #dbeafe;
  border-color: #bfdbfe;
  color: var(--accent-hover);
}
.art-badge.has-refs:hover { background: #bfdbfe; }
.art-badge.is-selected {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: #fff;
}

.xref-docs { margin-top: 28px; }
.xref-docs h3 {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-muted);
  margin-bottom: 10px;
}
.xref-doc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.doc-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 13px;
  border-radius: 999px;
  background: #dbeafe;
  color: var(--accent-hover);
  border: 1px solid #bfdbfe;
}
.doc-chip-count {
  font-weight: 700;
  font-size: 12px;
  color: var(--text-muted);
}

.xref-refs { margin-top: 24px; }
.xref-empty {
  font-size: 14px;
  color: var(--text-muted);
  font-style: italic;
}
.xref-ref-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.xref-ref {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 12px 14px;
}
.xref-ref-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 6px;
}
.xref-ref-doc {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-color);
}
.xref-ref-cite {
  font-size: 12px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.xref-ref-paragraph {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-main);
  white-space: pre-wrap;
}

.markdown :deep(h1) {
  font-size: 22px;
  margin: 24px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-color);
}
.markdown :deep(h1:first-child) { margin-top: 0; }
.markdown :deep(h2) { font-size: 18px; margin: 18px 0 8px; }
.markdown :deep(h3) { font-size: 16px; margin: 14px 0 6px; }
.markdown :deep(p) { margin: 0 0 12px; }
.markdown :deep(ul),
.markdown :deep(ol) { margin: 0 0 12px 1.25rem; }
.markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0 0 12px;
  font-size: 13px;
}
.markdown :deep(th),
.markdown :deep(td) {
  border: 1px solid var(--border-color);
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}
.markdown :deep(th) { background: #f8fafc; font-weight: 600; }
.markdown :deep(img) { max-width: 100%; height: auto; }
.markdown :deep(a) { color: var(--accent-color); }
.markdown :deep(code) {
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 4px;
  font-size: 0.9em;
}
</style>
