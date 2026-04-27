import { createRouter, createWebHistory } from 'vue-router';
import MunicipalitiesList from '../views/MunicipalitiesList.vue';
import MunicipalityDetails from '../views/MunicipalityDetails.vue';
const router = createRouter({
    history: createWebHistory(),
    routes: [
        { path: '/', name: 'municipalities', component: MunicipalitiesList },
        { path: '/details/:folder', name: 'details', component: MunicipalityDetails },
    ],
});
export default router;
