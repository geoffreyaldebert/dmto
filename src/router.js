import { createRouter, createWebHistory } from 'vue-router'
import MapView from './views/MapView.vue'
import MethodView from './views/MethodView.vue'

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'map', component: MapView },
    { path: '/methode', name: 'methode', component: MethodView },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})
