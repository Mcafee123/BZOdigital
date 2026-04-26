import { createRouter, createWebHistory } from 'vue-router';
import MunicipalitiesList from '../views/MunicipalitiesList.vue';
import MunicipalityDetails from '../views/MunicipalityDetails.vue';
import DiffPage from '../views/DiffPage.vue';
const router = createRouter({
    history: createWebHistory(),
    routes: [
        { path: '/', name: 'municipalities', component: MunicipalitiesList },
        { path: '/details/:folder', name: 'details', component: MunicipalityDetails },
        { path: '/diff', name: 'diff', component: DiffPage },
    ],
});
export default router;
