import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { marked } from 'marked';
import { api } from '../composables/useApi';
marked.setOptions({ gfm: true, breaks: false });
const route = useRoute();
const router = useRouter();
const folderName = route.params.folder;
const loading = ref(true);
const error = ref(null);
const data = ref(null);
const selected = ref(route.query.art || '');
const renderedBzo = computed(() => {
    if (!data.value)
        return '';
    return marked.parse(data.value.bzo_markdown);
});
const selectedRefs = computed(() => {
    if (!data.value || !selected.value)
        return [];
    return data.value.cross_references[selected.value] ?? [];
});
const selectedHasRefs = computed(() => selectedRefs.value.length > 0);
function docLabel(file, labels) {
    if (labels.length > 0)
        return labels[0];
    return file.replace(/\.md$/i, '');
}
const docTotals = computed(() => {
    if (!data.value)
        return [];
    const totals = new Map();
    for (const entries of Object.values(data.value.cross_references)) {
        for (const e of entries) {
            const key = e.source_file;
            const existing = totals.get(key);
            if (existing) {
                existing.count += 1;
            }
            else {
                totals.set(key, { key, label: docLabel(e.source_file, e.source_labels), count: 1 });
            }
        }
    }
    return [...totals.values()].sort((a, b) => b.count - a.count);
});
function badgeClass(art) {
    const has = (data.value?.cross_references[art]?.length ?? 0) > 0;
    return {
        'art-badge': true,
        'is-selected': art === selected.value,
        'has-refs': has && art !== selected.value,
        'no-refs': !has && art !== selected.value,
    };
}
function selectArticle(art) {
    selected.value = art;
    router.replace({ query: { ...route.query, art } });
    nextTick(() => {
        const el = document.querySelector(`a[name="art-${art}"]`);
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
        data.value = await api(`/api/municipalities/${folderName}/crossreferences`);
        if (!selected.value && data.value.articles.length > 0) {
            selected.value = data.value.articles[0];
        }
    }
    catch (err) {
        error.value = err.message || String(err);
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
/** @type {__VLS_StyleScopedClasses['xref-title']} */ ;
/** @type {__VLS_StyleScopedClasses['xref-header']} */ ;
/** @type {__VLS_StyleScopedClasses['xref-header']} */ ;
/** @type {__VLS_StyleScopedClasses['back-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['xref-error']} */ ;
/** @type {__VLS_StyleScopedClasses['art-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['art-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['art-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['has-refs']} */ ;
/** @type {__VLS_StyleScopedClasses['art-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['xref-docs']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "xref-view" },
});
/** @type {__VLS_StyleScopedClasses['xref-view']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "xref-header" },
});
/** @type {__VLS_StyleScopedClasses['xref-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "xref-title" },
});
/** @type {__VLS_StyleScopedClasses['xref-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({});
if (__VLS_ctx.data) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "xref-subtitle" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-subtitle']} */ ;
    (__VLS_ctx.data.municipality);
    (__VLS_ctx.data.bzo_filename);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.router.push(`/details/${__VLS_ctx.folderName}`);
            // @ts-ignore
            [data, data, data, router, folderName,];
        } },
    ...{ class: "back-btn" },
});
/** @type {__VLS_StyleScopedClasses['back-btn']} */ ;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "xref-loading" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-loading']} */ ;
}
else if (__VLS_ctx.error) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "xref-error" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-error']} */ ;
    (__VLS_ctx.error);
}
else if (__VLS_ctx.data) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "xref-grid" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-grid']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.article, __VLS_intrinsics.article)({
        ...{ class: "xref-doc markdown" },
    });
    __VLS_asFunctionalDirective(__VLS_directives.vHtml, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.renderedBzo) }, null, null);
    /** @type {__VLS_StyleScopedClasses['xref-doc']} */ ;
    /** @type {__VLS_StyleScopedClasses['markdown']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.aside, __VLS_intrinsics.aside)({
        ...{ class: "xref-side" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-side']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "xref-selected" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-selected']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({});
    (__VLS_ctx.selected || '—');
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "xref-count" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-count']} */ ;
    (__VLS_ctx.selectedHasRefs
        ? `${__VLS_ctx.selectedRefs.length} Querverweis${__VLS_ctx.selectedRefs.length === 1 ? '' : 'e'}`
        : 'Keine Querverweise');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "xref-articles" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-articles']} */ ;
    for (const [art] of __VLS_vFor((__VLS_ctx.data.articles))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.loading))
                        return;
                    if (!!(__VLS_ctx.error))
                        return;
                    if (!(__VLS_ctx.data))
                        return;
                    __VLS_ctx.selectArticle(art);
                    // @ts-ignore
                    [data, data, loading, error, error, renderedBzo, selected, selectedHasRefs, selectedRefs, selectedRefs, selectArticle,];
                } },
            key: (art),
            type: "button",
            ...{ class: (__VLS_ctx.badgeClass(art)) },
        });
        (art);
        // @ts-ignore
        [badgeClass,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "xref-docs" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-docs']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "xref-doc-chips" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-doc-chips']} */ ;
    for (const [d] of __VLS_vFor((__VLS_ctx.docTotals))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            key: (d.key),
            ...{ class: "doc-chip" },
        });
        /** @type {__VLS_StyleScopedClasses['doc-chip']} */ ;
        (d.label);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "doc-chip-count" },
        });
        /** @type {__VLS_StyleScopedClasses['doc-chip-count']} */ ;
        (d.count);
        // @ts-ignore
        [docTotals,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "xref-refs" },
    });
    /** @type {__VLS_StyleScopedClasses['xref-refs']} */ ;
    if (!__VLS_ctx.selectedHasRefs) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "xref-empty" },
        });
        /** @type {__VLS_StyleScopedClasses['xref-empty']} */ ;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
            ...{ class: "xref-ref-list" },
        });
        /** @type {__VLS_StyleScopedClasses['xref-ref-list']} */ ;
        for (const [r, i] of __VLS_vFor((__VLS_ctx.selectedRefs))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
                key: (i),
                ...{ class: "xref-ref" },
            });
            /** @type {__VLS_StyleScopedClasses['xref-ref']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "xref-ref-head" },
            });
            /** @type {__VLS_StyleScopedClasses['xref-ref-head']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "xref-ref-doc" },
            });
            /** @type {__VLS_StyleScopedClasses['xref-ref-doc']} */ ;
            (__VLS_ctx.docLabel(r.source_file, r.source_labels));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "xref-ref-cite" },
            });
            /** @type {__VLS_StyleScopedClasses['xref-ref-cite']} */ ;
            (r.citation_text);
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "xref-ref-paragraph" },
            });
            /** @type {__VLS_StyleScopedClasses['xref-ref-paragraph']} */ ;
            (r.paragraph);
            // @ts-ignore
            [selectedHasRefs, selectedRefs, docLabel,];
        }
    }
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
