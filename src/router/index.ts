import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/transects/:transectKey',
      name: 'transect',
      // Lazy: three.js and the viewer only load when a transect is opened (US-2.3).
      component: () => import('../views/TransectView.vue'),
      props: true,
    },
  ],
})

export default router
