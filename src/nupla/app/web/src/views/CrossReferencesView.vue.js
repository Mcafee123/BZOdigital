import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { marked } from 'marked';
import { diffWordsWithSpace } from 'diff';
import { api } from '../composables/useApi';
marked.setOptions({ gfm: true, breaks: false });
const route = useRoute();
const router = useRouter();
const folderName = route.params.folder;
const sections = ref(null);
const xrefs = ref(null);
const loading = ref(true);
const error = ref(null);
const selectedKey = ref(route.query.art || '');
const changedRows = computed(() => sections.value?.rows ?? []);
const currentRow = computed(() => {
    return changedRows.value.find((r) => r.key === selectedKey.value) ?? null;
});
const refsForCurrent = computed(() => {
    if (!selectedKey.value || !xrefs.value)
        return [];
    return xrefs.value.cross_references[selectedKey.value] ?? [];
});
function rowTitle(r) {
    return r.title_neu ?? r.title_alt ?? `Art. ${r.key}`;
}
function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function renderMd(src) {
    return marked.parse(src);
}
function renderNeuWithDiff(alt, neu) {
    const parts = diffWordsWithSpace(alt, neu);
    const merged = parts
        .filter((p) => !p.removed)
        .map((p) => (p.added ? `<mark class="diff-add">${escapeHtml(p.value)}</mark>` : p.value))
        .join('');
    return marked.parse(merged);
}
function renderNeuOrDiff(row) {
    return row.added ? renderMd(row.neu) : renderNeuWithDiff(row.alt, row.neu);
}
function docLabel(file, labels) {
    if (labels.length > 0)
        return labels[0];
    return file.replace(/\.md$/i, '');
}
function selectArticle(key) {
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
            api(`/api/municipalities/${folderName}/sections`),
            api(`/api/municipalities/${folderName}/crossreferences`),
        ]);
        sections.value = s;
        xrefs.value = x;
        if (!selectedKey.value && s.rows.length > 0) {
            selectArticle(s.rows[0].key);
        }
    }
    catch (e) {
        error.value = e.message || String(e);
    }
    finally {
        loading.value = false;
    }
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['detail-card-header']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-card-header']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-card-header']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['col']} */ ;
/** @type {__VLS_StyleScopedClasses['col']} */ ;
/** @type {__VLS_StyleScopedClasses['col']} */ ;
/** @type {__VLS_StyleScopedClasses['ref-detail']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-card-header']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-card-header']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['col']} */ ;
/** @type {__VLS_StyleScopedClasses['col']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "container detail-container" },
});
/** @type {__VLS_StyleScopedClasses['container']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-container']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.router.push(`/details/${__VLS_ctx.folderName}`);
            // @ts-ignore
            [router, folderName,];
        } },
    ...{ class: "back-btn" },
});
/** @type {__VLS_StyleScopedClasses['back-btn']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "detail-h1" },
});
/** @type {__VLS_StyleScopedClasses['detail-h1']} */ ;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "diff-status" },
    });
    /** @type {__VLS_StyleScopedClasses['diff-status']} */ ;
}
else if (__VLS_ctx.error) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "diff-status" },
        ...{ style: {} },
    });
    /** @type {__VLS_StyleScopedClasses['diff-status']} */ ;
    (__VLS_ctx.error);
}
else {
    if (__VLS_ctx.changedRows.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "topic-selector" },
        });
        /** @type {__VLS_StyleScopedClasses['topic-selector']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
            ...{ onChange: (...[$event]) => {
                    if (!!(__VLS_ctx.loading))
                        return;
                    if (!!(__VLS_ctx.error))
                        return;
                    if (!(__VLS_ctx.changedRows.length > 0))
                        return;
                    __VLS_ctx.selectArticle($event.target.value);
                    // @ts-ignore
                    [loading, error, error, changedRows, selectArticle,];
                } },
            value: (__VLS_ctx.selectedKey),
        });
        for (const [r] of __VLS_vFor((__VLS_ctx.changedRows))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                key: (r.key),
                value: (r.key),
            });
            (__VLS_ctx.rowTitle(r));
            // @ts-ignore
            [changedRows, selectedKey, rowTitle,];
        }
    }
    if (__VLS_ctx.currentRow) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "detail-card" },
        });
        /** @type {__VLS_StyleScopedClasses['detail-card']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
            ...{ class: "detail-card-header" },
        });
        /** @type {__VLS_StyleScopedClasses['detail-card-header']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "detail-card-body" },
        });
        /** @type {__VLS_StyleScopedClasses['detail-card-body']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "col col-alt" },
        });
        /** @type {__VLS_StyleScopedClasses['col']} */ ;
        /** @type {__VLS_StyleScopedClasses['col-alt']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
        (__VLS_ctx.currentRow.title_alt ?? __VLS_ctx.currentRow.title_neu);
        if (__VLS_ctx.currentRow.added) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cell-empty" },
            });
            /** @type {__VLS_StyleScopedClasses['cell-empty']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "markdown" },
            });
            __VLS_asFunctionalDirective(__VLS_directives.vHtml, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.renderMd(__VLS_ctx.currentRow.alt)) }, null, null);
            /** @type {__VLS_StyleScopedClasses['markdown']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "col col-neu" },
        });
        /** @type {__VLS_StyleScopedClasses['col']} */ ;
        /** @type {__VLS_StyleScopedClasses['col-neu']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
        (__VLS_ctx.currentRow.title_neu ?? __VLS_ctx.currentRow.title_alt);
        if (__VLS_ctx.currentRow.removed) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "cell-empty" },
            });
            /** @type {__VLS_StyleScopedClasses['cell-empty']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "markdown" },
            });
            __VLS_asFunctionalDirective(__VLS_directives.vHtml, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.renderNeuOrDiff(__VLS_ctx.currentRow)) }, null, null);
            /** @type {__VLS_StyleScopedClasses['markdown']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "col col-refs" },
        });
        /** @type {__VLS_StyleScopedClasses['col']} */ ;
        /** @type {__VLS_StyleScopedClasses['col-refs']} */ ;
        if (__VLS_ctx.refsForCurrent.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "ref-empty" },
            });
            /** @type {__VLS_StyleScopedClasses['ref-empty']} */ ;
        }
        for (const [r, i] of __VLS_vFor((__VLS_ctx.refsForCurrent))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.details, __VLS_intrinsics.details)({
                key: (i),
                ...{ class: "ref-detail" },
            });
            /** @type {__VLS_StyleScopedClasses['ref-detail']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.summary, __VLS_intrinsics.summary)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "ref-doc" },
            });
            /** @type {__VLS_StyleScopedClasses['ref-doc']} */ ;
            (__VLS_ctx.docLabel(r.source_file, r.source_labels));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "ref-cite" },
            });
            /** @type {__VLS_StyleScopedClasses['ref-cite']} */ ;
            (r.citation_text);
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "ref-paragraph" },
            });
            /** @type {__VLS_StyleScopedClasses['ref-paragraph']} */ ;
            (r.paragraph);
            // @ts-ignore
            [currentRow, currentRow, currentRow, currentRow, currentRow, currentRow, currentRow, currentRow, currentRow, renderMd, renderNeuOrDiff, refsForCurrent, refsForCurrent, docLabel,];
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "diff-status" },
        });
        /** @type {__VLS_StyleScopedClasses['diff-status']} */ ;
        (__VLS_ctx.selectedKey || '?');
    }
}
// @ts-ignore
[selectedKey,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
