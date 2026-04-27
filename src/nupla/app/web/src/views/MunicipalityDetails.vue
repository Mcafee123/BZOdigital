<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { marked } from 'marked';
import { diffWordsWithSpace } from 'diff';
import { api } from '../composables/useApi';
import DiffView from '../components/DiffView.vue';
import type { DiffPayload, SectionsPayload } from '../types/diff';

marked.setOptions({ gfm: true, breaks: false });

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
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

const route = useRoute();
const router = useRouter();

const folderName = route.params.folder as string;

const loading = ref(true);
const error = ref<string | null>(null);
const municipality = ref({ name: '', status: '' });
const pdfs = ref<any[]>([]);

const viewMode = ref<'overview' | 'diff'>('overview');

const sections = ref<SectionsPayload | null>(null);
const sectionsLoading = ref(false);
const sectionsMissing = ref(false);

const diffPayload = ref<DiffPayload | null>(null);
const diffLoading = ref(false);
const diffMissing = ref(false);

function articleTitle(row: { title_neu: string | null; title_alt: string | null }) {
  return row.title_neu ?? row.title_alt ?? '';
}

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
    return;
  } finally {
    loading.value = false;
  }

  sectionsLoading.value = true;
  diffLoading.value = true;
  await Promise.all([
    api<SectionsPayload>(`/api/municipalities/${folderName}/sections`)
      .then((d) => { sections.value = d; })
      .catch(() => { sectionsMissing.value = true; })
      .finally(() => { sectionsLoading.value = false; }),
    api<DiffPayload>(`/api/municipalities/${folderName}/diff`)
      .then((d) => { diffPayload.value = d; })
      .catch(() => { diffMissing.value = true; })
      .finally(() => { diffLoading.value = false; }),
  ]);
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

        <div class="toggle-wrapper">
          <button
            type="button"
            :class="{ active: viewMode === 'overview' }"
            @click="viewMode = 'overview'"
          >
            Übersicht
          </button>
          <button
            type="button"
            :class="{ active: viewMode === 'diff' }"
            @click="viewMode = 'diff'"
          >
            Diff
          </button>
        </div>

        <div v-if="viewMode === 'overview'">
          <div v-if="sectionsLoading" class="diff-status">Lädt Übersicht...</div>
          <div v-else-if="sectionsMissing" class="diff-status">Keine Übersicht verfügbar</div>
          <div v-else-if="sections && sections.rows.length === 0" class="diff-status">
            Keine geänderten Artikel gefunden.
          </div>
          <div v-else-if="sections" class="table-container">
            <table>
              <thead>
                <tr>
                  <th style="width: 50%;">Bisherige Bestimmung (Alt)</th>
                  <th style="width: 50%;">Geänderte Bestimmung (Neu)</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in sections.rows"
                  :key="row.key"
                  class="row-clickable"
                  @click="router.push(`/crossreferences/${folderName}?art=${encodeURIComponent(row.key)}`)"
                >
                  <td>
                    <strong>{{ articleTitle(row) }}</strong>
                    <div v-if="row.added" class="cell-empty">Neu eingefügt</div>
                    <div v-else class="cell-body markdown" v-html="renderMd(row.alt)"></div>
                  </td>
                  <td>
                    <strong>{{ articleTitle(row) }}</strong>
                    <div v-if="row.removed" class="cell-empty">Aufgehoben</div>
                    <div
                      v-else
                      class="cell-body markdown"
                      v-html="row.added ? renderMd(row.neu) : renderNeuWithDiff(row.alt, row.neu)"
                    ></div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-else class="diff-section">
          <div v-if="diffLoading" class="diff-status">Lädt Diff...</div>
          <div v-else-if="diffMissing" class="diff-status">Kein Diff verfügbar</div>
          <DiffView
            v-else-if="diffPayload"
            :unified-diff="diffPayload.unified_diff"
            :left-filename="diffPayload.left_filename"
            :right-filename="diffPayload.right_filename"
            mode="split"
          />
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.toggle-wrapper {
  display: inline-flex;
  background: #f1f5f9;
  padding: 4px;
  border-radius: 10px;
  margin-bottom: 24px;
}
.toggle-wrapper button {
  padding: 8px 24px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
}
.toggle-wrapper button.active {
  background: var(--surface-color);
  color: var(--text-main);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.table-container {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}
.table-container table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
.table-container th,
.table-container td {
  padding: 20px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid var(--border-color);
}
.table-container tr:last-child td {
  border-bottom: none;
}
.table-container th {
  background: #f8fafc;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  font-weight: 600;
}
.table-container td {
  font-size: 15px;
}
.cell-body {
  margin-top: 12px;
}
.cell-empty {
  margin-top: 12px;
  color: var(--text-muted);
  font-style: italic;
}

.markdown :deep(p) {
  margin: 0 0 12px;
}
.markdown :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown :deep(ul),
.markdown :deep(ol) {
  margin: 0 0 12px 1.25rem;
}
.markdown :deep(blockquote) {
  margin: 0 0 12px;
  padding: 4px 12px;
  border-left: 3px solid var(--border-color);
  color: var(--text-muted);
}
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
.markdown :deep(th) {
  background: #f8fafc;
  font-weight: 600;
}
.markdown :deep(img) {
  max-width: 100%;
  height: auto;
}
.markdown :deep(code) {
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 4px;
  font-size: 0.9em;
}
.markdown :deep(mark.diff-add) {
  background: #dcfce7;
  color: var(--text-main);
  padding: 0 2px;
  border-radius: 3px;
}

.diff-section {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.diff-status {
  color: var(--text-muted);
  font-size: 14px;
}
</style>
