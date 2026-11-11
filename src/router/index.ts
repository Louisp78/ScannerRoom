import { createRouter, createWebHistory } from 'vue-router'
import { getMe, getTransect } from '@/api'
import LandingView from '../views/LandingView.vue'

declare module 'vue-router' {
  interface RouteMeta {
    /** Reserved to signed-in users (US-4.2); the API enforces it on the data as well. */
    requiresAuth?: boolean
  }
}

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
      meta: { requiresAuth: true },
      // Lazy: the globe pulls in three.js, which the landing page does not need.
      component: () => import('../views/ExploreView.vue'),
    },
    {
      path: '/transects/:transectKey',
      name: 'transect',
      meta: { requiresAuth: true },
      // Lazy: three.js and the viewer only load when a transect is opened (US-2.3).
      component: () => import('../views/TransectView.vue'),
      props: true,
    },
    {
      path: '/sign-in',
      name: 'sign-in',
      component: () => import('../views/SignInView.vue'),
    },
    {
      path: '/request-access',
      name: 'request-access',
      component: () => import('../views/RequestAccessView.vue'),
    },
    // Local ingest tool: its endpoint only exists on the dev server
    // (vite-plugins/ingest.ts), so the page is left out of production builds;
    // there, "Add a transect" leads to the access request page instead.
    ...(import.meta.env.DEV
      ? [{ path: '/ingest', name: 'ingest', component: () => import('../views/IngestView.vue') }]
      : []),
  ],
})

/**
 * Sends signed-out visitors of reserved pages to the sign-in page. This is
 * only the user-facing side: the API and nginx refuse the data itself.
 */
router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth || (await getMe())) return true
  // Showcase transects (e.g. the one on the landing page) stay open to everyone:
  // the API only answers for them when signed out.
  if (to.name === 'transect' && (await getTransect(String(to.params.transectKey)))) return true
  return { name: 'sign-in', query: { redirect: to.fullPath } }
})

export default router
