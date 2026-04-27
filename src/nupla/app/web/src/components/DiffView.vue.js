import { computed } from 'vue';
import { DiffView as GitDiffView, DiffModeEnum } from '@git-diff-view/vue';
import '@git-diff-view/vue/styles/diff-view.css';
const props = defineProps();
const diffMode = computed(() => props.mode === 'split' ? DiffModeEnum.Split : DiffModeEnum.Unified);
const diffData = computed(() => ({
    oldFile: {
        fileName: props.leftFilename,
        fileLang: 'markdown',
        content: props.leftContent ?? '',
    },
    newFile: {
        fileName: props.rightFilename,
        fileLang: 'markdown',
        content: props.rightContent ?? '',
    },
    hunks: [props.unifiedDiff],
}));
const isEmpty = computed(() => !props.unifiedDiff);
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "diff-view-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['diff-view-wrapper']} */ ;
if (__VLS_ctx.isEmpty) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "center-align padding" },
    });
    /** @type {__VLS_StyleScopedClasses['center-align']} */ ;
    /** @type {__VLS_StyleScopedClasses['padding']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.i, __VLS_intrinsics.i)({
        ...{ class: "extra" },
    });
    /** @type {__VLS_StyleScopedClasses['extra']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
}
else {
    let __VLS_0;
    /** @ts-ignore @type {typeof __VLS_components.GitDiffView} */
    GitDiffView;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        data: (__VLS_ctx.diffData),
        diffViewMode: (__VLS_ctx.diffMode),
        diffViewWrap: (true),
        diffViewHighlight: (true),
        diffViewAddWidget: (false),
    }));
    const __VLS_2 = __VLS_1({
        data: (__VLS_ctx.diffData),
        diffViewMode: (__VLS_ctx.diffMode),
        diffViewWrap: (true),
        diffViewHighlight: (true),
        diffViewAddWidget: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
// @ts-ignore
[isEmpty, diffData, diffMode,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
