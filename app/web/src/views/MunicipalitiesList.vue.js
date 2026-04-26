import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useMunicipalities } from '../composables/useMunicipalities';
const router = useRouter();
const { municipalities, loading, error, fetchMunicipalities } = useMunicipalities();
const searchQuery = ref('');
const isDropdownOpen = ref(false);
const filteredMunicipalities = computed(() => {
    if (!searchQuery.value)
        return municipalities.value;
    const q = searchQuery.value.toLowerCase();
    return municipalities.value.filter(m => m.name.toLowerCase().includes(q));
});
const selectMunicipality = (folder) => {
    searchQuery.value = '';
    isDropdownOpen.value = false;
    router.push({ name: 'details', params: { folder } });
};
const handleFocusOut = () => {
    setTimeout(() => {
        isDropdownOpen.value = false;
    }, 200);
};
onMounted(() => {
    fetchMunicipalities();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['dropdown-item']} */ ;
/** @type {__VLS_StyleScopedClasses['dropdown-item']} */ ;
/** @type {__VLS_StyleScopedClasses['dropdown-item']} */ ;
/** @type {__VLS_StyleScopedClasses['dropdown-item']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    id: "view-home",
    ...{ class: "view active" },
});
/** @type {__VLS_StyleScopedClasses['view']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "logo" },
});
/** @type {__VLS_StyleScopedClasses['logo']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "subtitle" },
});
/** @type {__VLS_StyleScopedClasses['subtitle']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ onFocusout: (__VLS_ctx.handleFocusOut) },
    ...{ class: "search-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['search-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    ...{ onFocus: (...[$event]) => {
            __VLS_ctx.isDropdownOpen = true;
            // @ts-ignore
            [handleFocusOut, isDropdownOpen,];
        } },
    type: "text",
    value: (__VLS_ctx.searchQuery),
    placeholder: "Gemeinde suchen (z.B. Bern)...",
    autocomplete: "off",
});
if (__VLS_ctx.isDropdownOpen && !__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "dropdown" },
    });
    /** @type {__VLS_StyleScopedClasses['dropdown']} */ ;
    if (__VLS_ctx.filteredMunicipalities.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "dropdown-item empty" },
        });
        /** @type {__VLS_StyleScopedClasses['dropdown-item']} */ ;
        /** @type {__VLS_StyleScopedClasses['empty']} */ ;
    }
    else {
        for (const [muni] of __VLS_vFor((__VLS_ctx.filteredMunicipalities))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.isDropdownOpen && !__VLS_ctx.loading))
                            return;
                        if (!!(__VLS_ctx.filteredMunicipalities.length === 0))
                            return;
                        __VLS_ctx.selectMunicipality(muni.folder);
                        // @ts-ignore
                        [isDropdownOpen, searchQuery, loading, filteredMunicipalities, filteredMunicipalities, selectMunicipality,];
                    } },
                key: (muni.folder),
                ...{ class: "dropdown-item" },
            });
            /** @type {__VLS_StyleScopedClasses['dropdown-item']} */ ;
            (muni.name);
            // @ts-ignore
            [];
        }
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "search-hint" },
});
/** @type {__VLS_StyleScopedClasses['search-hint']} */ ;
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ style: {} },
    });
    (__VLS_ctx.error);
}
// @ts-ignore
[error, error,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
