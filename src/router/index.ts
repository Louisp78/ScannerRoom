import { createRouter, createWebHistory } from 'vue-router'
import LandingView from '../views/LandingView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: LandingView,
    },
    {
      path: '/explore',
      name: 'explore',
      // Lazy: the globe pulls in three.js, which the landing page does not need.
      component: () => import('../views/ExploreView.vue'),
    },
    {
      path: '/transects/:transectKey',
      name: 'transect',
      // Lazy: three.js and the viewer only load when a transect is opened (US-2.3).
      component: () => import('../views/TransectView.vue'),
      props: true,
    },
    // Local ingest tool: its endpoint only exists on the dev server
    // (vite-plugins/ingest.ts), so the page is left out of production builds.
    ...(import.meta.env.DEV
      ? [{ path: '/ingest', name: 'ingest', component: () => import('../views/IngestView.vue') }]
      : []),
  ],
})

export default router
