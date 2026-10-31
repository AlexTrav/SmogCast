import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

// главная грузится сразу, остальные страницы – отдельными чанками при первом переходе
const soon = () => import('../views/SoonView.vue')

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/history', name: 'history', component: () => import('../views/HistoryView.vue') },
    { path: '/models', name: 'models', component: soon },
    { path: '/performance', name: 'performance', component: soon },
    { path: '/about', name: 'about', component: soon },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
})

export default router
