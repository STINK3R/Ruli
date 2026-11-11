/* Service worker «Рули»: приложение открывается без сети, карта и фото машин — из кэша.

   Стратегии:
   - страницы (навигация) — сначала сеть, без сети — сохранённая оболочка, иначе offline.html;
   - собранные файлы /assets/* (в имени хэш) — из кэша, навсегда;
   - иконки, фото машин, шрифты, плитки карты — из кэша с фоновым обновлением;
   - /api/, /admin/, /media/ — только сеть: бронь, деньги и документы не кэшируются никогда. */

const VERSION = 'ruli-v3'
const SHELL = `${VERSION}-shell`
const STATIC = `${VERSION}-static`
const RUNTIME = `${VERSION}-runtime`
const TILES = `${VERSION}-tiles`
const MAX_TILES = 600
const MAX_RUNTIME = 120

const PRECACHE = [
  '/',
  '/offline.html',
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/apple-touch-icon.png',
  '/favicon.svg',
]

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(PRECACHE)))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(keys.filter((key) => !key.startsWith(VERSION)).map((key) => caches.delete(key)))
      await self.clients.claim()
    })(),
  )
})

// Приложение само решает, когда обновиться: показывает «Доступна новая версия».
self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting()
})

async function trim(cacheName, max) {
  const cache = await caches.open(cacheName)
  const keys = await cache.keys()
  for (let i = 0; i < keys.length - max; i += 1) await cache.delete(keys[i])
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request)
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok) (await caches.open(cacheName)).put(request, response.clone())
  return response
}

async function staleWhileRevalidate(request, cacheName, max) {
  const cache = await caches.open(cacheName)
  const cached = await cache.match(request)
  const network = fetch(request)
    .then((response) => {
      if (response.ok || response.type === 'opaque') {
        cache.put(request, response.clone()).then(() => max && trim(cacheName, max))
      }
      return response
    })
    .catch(() => cached)
  return cached || network
}

async function navigation(request) {
  try {
    const response = await fetch(request)
    if (response.ok) (await caches.open(SHELL)).put('/', response.clone())
    return response
  } catch {
    return (await caches.match('/')) || (await caches.match('/offline.html'))
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return
  const url = new URL(request.url)

  if (url.origin === self.location.origin) {
    if (/^\/(api|admin|media|static)\//.test(url.pathname)) return // только сеть
    if (request.mode === 'navigate') {
      event.respondWith(navigation(request))
      return
    }
    if (url.pathname.startsWith('/assets/')) {
      event.respondWith(cacheFirst(request, STATIC))
      return
    }
    if (/^\/(icons|cars)\/|\.(png|webp|svg|woff2?)$/.test(url.pathname)) {
      event.respondWith(staleWhileRevalidate(request, RUNTIME, MAX_RUNTIME))
    }
    return
  }

  // Векторные плитки и стиль OpenFreeMap: карта видна сразу, даже при слабой сети.
  if (url.hostname.endsWith('openfreemap.org')) {
    event.respondWith(staleWhileRevalidate(request, TILES, MAX_TILES))
  }
})
