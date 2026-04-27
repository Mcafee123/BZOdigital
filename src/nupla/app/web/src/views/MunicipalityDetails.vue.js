import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
const route = useRoute();
const router = useRouter();
const folderName = route.params.folder;
const loading = ref(true);
const error = ref(null);
const municipality = ref({ name: '', status: '' });
const pdfs = ref([]);
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
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
