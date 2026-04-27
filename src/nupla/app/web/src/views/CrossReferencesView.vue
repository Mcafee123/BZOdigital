<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { marked } from 'marked';
import { diffWordsWithSpace } from 'diff';
import { api } from '../composables/useApi';
import type { SectionRow, SectionsPayload } from '../types/diff';
import type { CrossReferenceEntry, CrossReferencesPayload } from '../types/crossreferences';

marked.setOptions({ gfm: true, breaks: false });

const route = useRoute();
const router = useRouter();
const folderName = route.params.folder as string;

const sections = ref<SectionsPayload | null>(null);
const xrefs = ref<CrossReferencesPayload | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const selectedKey = ref<string>((route.query.art as string) || '');

const changedRows = computed<SectionRow[]>(() => sections.value?.rows ?? []);
const currentRow = computed<SectionRow | null>(() => {
  return changedRows.value.find((r) => r.key === selectedKey.value) ?? null;
});
const refsForCurrent = computed<CrossReferenceEntry[]>(() => {
  if (!selectedKey.value || !xrefs.value) return [];
  return xrefs.value.cross_references[selectedKey.value] ?? [];
});

function rowTitle(r: SectionRow): string {
  return r.title_neu ?? r.title_alt ?? `Art. ${r.key}`;
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function renderMd(src: string): string {
  return marked.parse(src) as string;
}

function renderNeuWithDiff(alt: string, neu: string): string {
  const parts = diffWordsWithSpace(alt, neu);
  const merged = parts
    .filter((p) => !p.removed)
    .map((p) => (p.added ? `<mark class="diff-add">${escapeHtml(p.value)}</mark>` : p.value))
    .join('');
  return marked.parse(merged) as string;
}

function renderNeuOrDiff(row: SectionRow): string {
  return row.added ? renderMd(row.neu) : renderNeuWithDiff(row.alt, row.neu);
}

function docLabel(file: string, labels: string[]): string {
  if (labels.length > 0) return labels[0];
  return file.replace(/\.md$/i, '');
}

function selectArticle(key: string) {
  selectedKey.value = key;
  router.replace({ query: { ...route.query, art: key } });
}

watch(() => route.query.art, (q) => {
  if (typeof q === 'string' && q !== selectedKey.value) {
    selectedKey.value = q;
  }
});

onMounted(async () => {
  try {
    const [s, x] = await Promise.all([
      api<SectionsPayload>(`/api/municipalities/${folderName}/sections`),
      api<CrossReferencesPayload>(`/api/municipalities/${folderName}/crossreferences`),
    ]);
    sections.value = s;
    xrefs.value = x;
    if (!selectedKey.value && s.rows.length > 0) {
      selectArticle(s.rows[0].key);
    }
  } catch (e: any) {
    error.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="container detail-container">
    <a class="back-btn" @click.prevent="router.push(`/details/${folderName}`)">
      ← Zurück zur Übersicht
    </a>

    <h1 class="detail-h1">Details</h1>

    <div v-if="loading" class="diff-status">Lädt...</div>
    <div v-else-if="error" class="diff-status" style="color:#b91c1c">{{ error }}</div>

    <template v-else>
      <div class="topic-selector" v-if="changedRows.length > 0">
        <select :value="selectedKey" @change="selectArticle(($event.target as HTMLSelectElement).value)">
          <option v-for="r in changedRows" :key="r.key" :value="r.key">
            Thema: {{ rowTitle(r) }}
          </option>
        </select>
      </div>

      <div v-if="currentRow" class="detail-card">
        <header class="detail-card-header">
          <div>Bisher (Alt)</div>
          <div>Geplant (Neu)</div>
          <div>Referenzen &amp; Quellen</div>
        </header>
        <div class="detail-card-body">
          <div class="col col-alt">
            <strong>{{ currentRow.title_alt ?? currentRow.title_neu }}</strong>
            <div v-if="currentRow.added" class="cell-empty">Neu eingefügt</div>
            <div v-else class="markdown" v-html="renderMd(currentRow.alt)"></div>
          </div>
          <div class="col col-neu">
            <strong>{{ currentRow.title_neu ?? currentRow.title_alt }}</strong>
            <div v-if="currentRow.removed" class="cell-empty">Aufgehoben</div>
            <div v-else class="markdown" v-html="renderNeuOrDiff(currentRow)"></div>
          </div>
          <div class="col col-refs">
            <p v-if="refsForCurrent.length === 0" class="ref-empty">
              Keine Querverweise in Begleitdokumenten.
            </p>
            <details v-for="(r, i) in refsForCurrent" :key="i" class="ref-detail">
              <summary>
                <span class="ref-doc">{{ docLabel(r.source_file, r.source_labels) }}</span>
                <span class="ref-cite">{{ r.citation_text }}</span>
              </summary>
              <div class="ref-paragraph markdown" v-html="renderMd(r.paragraph_html ?? r.paragraph)"></div>
            </details>
          </div>
        </div>
      </div>

      <div v-else class="diff-status">
        Artikel {{ selectedKey || '?' }} nicht in den geänderten Bestimmungen gefunden.
      </div>
    </template>
  </div>
</template>

<style scoped>
.detail-container {
  max-width: 1280px;
}
.detail-h1 {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.4px;
  margin-bottom: 20px;
}

.topic-selector {
  margin-bottom: 24px;
}

.detail-card {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}
.detail-card-header,
.detail-card-body {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
}
.detail-card-header {
  background: #f8fafc;
  border-bottom: 1px solid var(--border-color);
}
.detail-card-header > div {
  padding: 16px 20px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  font-weight: 600;
}
.detail-card-header > div + div,
.detail-card-body > .col + .col {
  border-left: 1px solid var(--border-color);
}

.col {
  padding: 20px;
  font-size: 15px;
  line-height: 1.6;
  vertical-align: top;
  min-width: 0;
}
.col strong {
  display: block;
  margin-bottom: 12px;
}
.cell-empty {
  color: var(--text-muted);
  font-style: italic;
}

.ref-empty {
  color: var(--text-muted);
  font-style: italic;
  font-size: 14px;
}
.ref-detail {
  margin-bottom: 8px;
}
.ref-detail :deep(summary) {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ref-doc {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ref-cite {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.ref-paragraph {
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.5;
}

.markdown :deep(p) { margin: 0 0 12px; }
.markdown :deep(p:last-child) { margin-bottom: 0; }
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
.markdown :deep(mark.diff-add) {
  background: #dcfce7;
  color: var(--text-main);
  padding: 0 2px;
  border-radius: 3px;
}
.markdown :deep(mark.cite) {
  background: #fef08a;
  color: var(--text-main);
  padding: 0 2px;
  border-radius: 3px;
}

@media (max-width: 900px) {
  .detail-card-header,
  .detail-card-body {
    grid-template-columns: 1fr;
  }
  .detail-card-header > div + div,
  .detail-card-body > .col + .col {
    border-left: none;
    border-top: 1px solid var(--border-color);
  }
}
</style>
