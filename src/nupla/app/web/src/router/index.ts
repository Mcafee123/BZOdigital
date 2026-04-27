import { createRouter, createWebHistory } from 'vue-router'
import MunicipalitiesList from '../views/MunicipalitiesList.vue'
import MunicipalityDetails from '../views/MunicipalityDetails.vue'
import CrossReferencesView from '../views/CrossReferencesView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'municipalities', component: MunicipalitiesList },
    { path: '/details/:folder', name: 'details', component: MunicipalityDetails },
    { path: '/crossreferences/:folder', name: 'crossreferences', component: CrossReferencesView },
  ],
})

export default router
