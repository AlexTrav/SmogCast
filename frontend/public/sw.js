// service worker SmogCast: сайт открывается и без сети – с последним сохранённым прогнозом.
// Оболочка (index.html) и ответы API – «сначала сеть, при ошибке – кэш»; файлы сборки с хэшем в имени
// не меняются – «сначала кэш»
const SHELL = 'smogcast-shell-v1'
const DATA = 'smogcast-data-v1'
const API = 'https://smogcast-backend.onrender.com/api/'

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(['./', './index.html'])))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => ![SHELL, DATA].includes(k)).map((k) => caches.delete(k)))),
  )
  self.clients.claim()
})

async function networkFirst(request, cacheName, fallback) {
  const cache = await caches.open(cacheName)
  try {
    const response = await fetch(request)
    if (response.ok) cache.put(fallback ?? request, response.clone())
    return response
  } catch (error) {
    const cached = await cache.match(fallback ?? request)
    if (cached) return cached
    throw error
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(SHELL)
  const cached = await cache.match(request)
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok) cache.put(request, response.clone())
  return response
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  // /api/health будит сервер – его не кэшируем, чтобы плашка «просыпается» была честной
  if (request.url.startsWith(API) && !url.pathname.endsWith('/health')) {
    event.respondWith(networkFirst(request, DATA))
  } else if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, SHELL, './index.html'))
  } else if (url.origin === self.location.origin && url.pathname.includes('/assets/')) {
    event.respondWith(cacheFirst(request))
  }
})
