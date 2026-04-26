import { createRouter, createWebHistory } from 'vue-router'
import DiffPage from '../views/DiffPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'diff', component: DiffPage },
  ],
})

export default router
