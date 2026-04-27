import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { marked } from 'marked';
import { diffWordsWithSpace } from 'diff';
import { api } from '../composables/useApi';
import DiffView from '../components/DiffView.vue';
marked.setOptions({ gfm: true, breaks: false });
function escapeHtml(s) {
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
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
const route = useRoute();
const router = useRouter();
const folderName = route.params.folder;
const loading = ref(true);
const error = ref(null);
const municipality = ref({ name: '', status: '' });
const pdfs = ref([]);
const viewMode = ref('overview');
const sections = ref(null);
const sectionsLoading = ref(false);
const sectionsMissing = ref(false);
const diffPayload = ref(null);
const diffLoading = ref(false);
const diffMissing = ref(false);
function articleTitle(row) {
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
    }
    catch (err) {
        error.value = err.message;
        return;
    }
    finally {
        loading.value = false;
    }
    sectionsLoading.value = true;
    diffLoading.value = true;
    await Promise.all([
        api(`/api/municipalities/${folderName}/sections`)
            .then((d) => { sections.value = d; })
            .catch(() => { sectionsMissing.value = true; })
            .finally(() => { sectionsLoading.value = false; }),
        api(`/api/municipalities/${folderName}/diff`)
            .then((d) => { diffPayload.value = d; })
            .catch(() => { diffMissing.value = true; })
            .finally(() => { diffLoading.value = false; }),
    ]);
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['toggle-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-link']} */ ;
/** @type {__VLS_StyleScopedClasses['table-container']} */ ;
/** @type {__VLS_StyleScopedClasses['table-container']} */ ;
/** @type {__VLS_StyleScopedClasses['table-container']} */ ;
/** @type {__VLS_StyleScopedClasses['table-container']} */ ;
/** @type {__VLS_StyleScopedClasses['table-container']} */ ;
/** @type {__VLS_StyleScopedClasses['table-container']} */ ;
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
    id: "view-municipality",
    ...{ class: "view active" },
});
/** @type {__VLS_StyleScopedClasses['view']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "container" },
});
/** @type {__VLS_StyleScopedClasses['container']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.router.push('/');
            // @ts-ignore
            [router,];
        } },
    ...{ class: "back-btn" },
});
/** @type {__VLS_StyleScopedClasses['back-btn']} */ ;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
}
else if (__VLS_ctx.error) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ style: {} },
    });
    (__VLS_ctx.error);
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "header-section" },
    });
    /** @type {__VLS_StyleScopedClasses['header-section']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_ctx.municipality.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "status-badge" },
    });
    /** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
    (__VLS_ctx.municipality.status);
    if (__VLS_ctx.pdfs.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "documents-row" },
        });
        /** @type {__VLS_StyleScopedClasses['documents-row']} */ ;
        for (const [pdf] of __VLS_vFor((__VLS_ctx.pdfs))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
                key: (pdf.id),
                href: (pdf.url),
                target: "_blank",
                ...{ class: "doc-card" },
            });
            /** @type {__VLS_StyleScopedClasses['doc-card']} */ ;
            (pdf.label);
            // @ts-ignore
            [loading, error, error, municipality, municipality, pdfs, pdfs,];
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ style: {} },
        });
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "toggle-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['toggle-wrapper']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(__VLS_ctx.loading))
                    return;
                if (!!(__VLS_ctx.error))
                    return;
                __VLS_ctx.viewMode = 'overview';
                // @ts-ignore
                [viewMode,];
            } },
        type: "button",
        ...{ class: ({ active: __VLS_ctx.viewMode === 'overview' }) },
    });
    /** @type {__VLS_StyleScopedClasses['active']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(__VLS_ctx.loading))
                    return;
                if (!!(__VLS_ctx.error))
                    return;
                __VLS_ctx.viewMode = 'diff';
                // @ts-ignore
                [viewMode, viewMode,];
            } },
        type: "button",
        ...{ class: ({ active: __VLS_ctx.viewMode === 'diff' }) },
    });
    /** @type {__VLS_StyleScopedClasses['active']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(__VLS_ctx.loading))
                    return;
                if (!!(__VLS_ctx.error))
                    return;
                __VLS_ctx.router.push(`/crossreferences/${__VLS_ctx.folderName}`);
                // @ts-ignore
                [router, viewMode, folderName,];
            } },
        type: "button",
        ...{ class: "toggle-link" },
    });
    /** @type {__VLS_StyleScopedClasses['toggle-link']} */ ;
    if (__VLS_ctx.viewMode === 'overview') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        if (__VLS_ctx.sectionsLoading) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "diff-status" },
            });
            /** @type {__VLS_StyleScopedClasses['diff-status']} */ ;
        }
        else if (__VLS_ctx.sectionsMissing) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "diff-status" },
            });
            /** @type {__VLS_StyleScopedClasses['diff-status']} */ ;
        }
        else if (__VLS_ctx.sections && __VLS_ctx.sections.rows.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "diff-status" },
            });
            /** @type {__VLS_StyleScopedClasses['diff-status']} */ ;
        }
        else if (__VLS_ctx.sections) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "table-container" },
            });
            /** @type {__VLS_StyleScopedClasses['table-container']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                ...{ style: {} },
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                ...{ style: {} },
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
            for (const [row] of __VLS_vFor((__VLS_ctx.sections.rows))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                    key: (row.key),
                });
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
                __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
                (__VLS_ctx.articleTitle(row));
                if (row.added) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                        ...{ class: "cell-empty" },
                    });
                    /** @type {__VLS_StyleScopedClasses['cell-empty']} */ ;
                }
                else {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                        ...{ class: "cell-body markdown" },
                    });
                    __VLS_asFunctionalDirective(__VLS_directives.vHtml, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.renderMd(row.alt)) }, null, null);
                    /** @type {__VLS_StyleScopedClasses['cell-body']} */ ;
                    /** @type {__VLS_StyleScopedClasses['markdown']} */ ;
                }
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
                __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
                (__VLS_ctx.articleTitle(row));
                if (row.removed) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                        ...{ class: "cell-empty" },
                    });
                    /** @type {__VLS_StyleScopedClasses['cell-empty']} */ ;
                }
                else {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                        ...{ class: "cell-body markdown" },
                    });
                    __VLS_asFunctionalDirective(__VLS_directives.vHtml, {})(null, { ...__VLS_directiveBindingRestFields, value: (row.added ? __VLS_ctx.renderMd(row.neu) : __VLS_ctx.renderNeuWithDiff(row.alt, row.neu)) }, null, null);
                    /** @type {__VLS_StyleScopedClasses['cell-body']} */ ;
                    /** @type {__VLS_StyleScopedClasses['markdown']} */ ;
                }
                // @ts-ignore
                [viewMode, sectionsLoading, sectionsMissing, sections, sections, sections, sections, articleTitle, articleTitle, renderMd, renderMd, renderNeuWithDiff,];
            }
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "diff-section" },
        });
        /** @type {__VLS_StyleScopedClasses['diff-section']} */ ;
        if (__VLS_ctx.diffLoading) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "diff-status" },
            });
            /** @type {__VLS_StyleScopedClasses['diff-status']} */ ;
        }
        else if (__VLS_ctx.diffMissing) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "diff-status" },
            });
            /** @type {__VLS_StyleScopedClasses['diff-status']} */ ;
        }
        else if (__VLS_ctx.diffPayload) {
            const __VLS_0 = DiffView;
            // @ts-ignore
            const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
                unifiedDiff: (__VLS_ctx.diffPayload.unified_diff),
                leftFilename: (__VLS_ctx.diffPayload.left_filename),
                rightFilename: (__VLS_ctx.diffPayload.right_filename),
                mode: "split",
            }));
            const __VLS_2 = __VLS_1({
                unifiedDiff: (__VLS_ctx.diffPayload.unified_diff),
                leftFilename: (__VLS_ctx.diffPayload.left_filename),
                rightFilename: (__VLS_ctx.diffPayload.right_filename),
                mode: "split",
            }, ...__VLS_functionalComponentArgsRest(__VLS_1));
        }
    }
}
// @ts-ignore
[diffLoading, diffMissing, diffPayload, diffPayload, diffPayload, diffPayload,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
