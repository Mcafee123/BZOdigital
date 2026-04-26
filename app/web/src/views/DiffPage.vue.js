import { onMounted, ref } from 'vue';
import { useDiffStore } from '../stores/diff';
import DiffView from '../components/DiffView.vue';
const store = useDiffStore();
const mode = ref('unified');
onMounted(() => {
    void store.load();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
    ...{ class: "diff-page" },
});
/** @type {__VLS_StyleScopedClasses['diff-page']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar padding" },
});
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['padding']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "tabs" },
});
/** @type {__VLS_StyleScopedClasses['tabs']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.mode = 'unified';
            // @ts-ignore
            [mode,];
        } },
    ...{ class: ({ active: __VLS_ctx.mode === 'unified' }) },
});
/** @type {__VLS_StyleScopedClasses['active']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.mode = 'split';
            // @ts-ignore
            [mode, mode,];
        } },
    ...{ class: ({ active: __VLS_ctx.mode === 'split' }) },
});
/** @type {__VLS_StyleScopedClasses['active']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.store.load();
            // @ts-ignore
            [mode, store,];
        } },
    ...{ class: "border" },
    disabled: (__VLS_ctx.store.loading),
});
/** @type {__VLS_StyleScopedClasses['border']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.i, __VLS_intrinsics.i)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
if (__VLS_ctx.store.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "center-align padding" },
    });
    /** @type {__VLS_StyleScopedClasses['center-align']} */ ;
    /** @type {__VLS_StyleScopedClasses['padding']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.progress, __VLS_intrinsics.progress)({
        ...{ class: "circle" },
    });
    /** @type {__VLS_StyleScopedClasses['circle']} */ ;
}
else if (__VLS_ctx.store.error) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.article, __VLS_intrinsics.article)({
        ...{ class: "error padding" },
    });
    /** @type {__VLS_StyleScopedClasses['error']} */ ;
    /** @type {__VLS_StyleScopedClasses['padding']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.i, __VLS_intrinsics.i)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_ctx.store.error);
}
else {
    const __VLS_0 = DiffView;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        unifiedDiff: (__VLS_ctx.store.unifiedDiff),
        leftFilename: (__VLS_ctx.store.leftFilename),
        rightFilename: (__VLS_ctx.store.rightFilename),
        mode: (__VLS_ctx.mode),
    }));
    const __VLS_2 = __VLS_1({
        unifiedDiff: (__VLS_ctx.store.unifiedDiff),
        leftFilename: (__VLS_ctx.store.leftFilename),
        rightFilename: (__VLS_ctx.store.rightFilename),
        mode: (__VLS_ctx.mode),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
// @ts-ignore
[mode, store, store, store, store, store, store, store,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
