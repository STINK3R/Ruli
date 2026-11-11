// PWA: регистрация service worker и перехват предложения установки.
// Модуль импортируется в main.jsx первым — событие beforeinstallprompt приходит рано,
// до того как React успеет смонтировать компоненты.

const INSTALLED_KEY = 'ruli:installed'
const listeners = new Set()

let deferredPrompt = null
let waitingWorker = null

const emit = () => listeners.forEach((listener) => listener())

export function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (event) => {
    // Своё окно с объяснением вместо мини-баннера браузера.
    event.preventDefault()
    deferredPrompt = event
    emit()
  })
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null
    markInstalled()
  })
  window.matchMedia?.('(display-mode: standalone)').addEventListener?.('change', emit)
}

export function markInstalled() {
  try {
    localStorage.setItem(INSTALLED_KEY, '1')
  } catch {
    /* без localStorage просто покажем подсказку ещё раз */
  }
  emit()
}

/** Открыто как установленное приложение (с главного экрана), а не во вкладке браузера. */
export function isStandalone() {
  return Boolean(
    window.matchMedia?.('(display-mode: standalone)').matches ||
      window.matchMedia?.('(display-mode: minimal-ui)').matches ||
      window.navigator.standalone,
  )
}

export function wasInstalled() {
  try {
    return localStorage.getItem(INSTALLED_KEY) === '1'
  } catch {
    return false
  }
}

export function canPrompt() {
  return Boolean(deferredPrompt)
}

export async function promptInstall() {
  if (!deferredPrompt) return 'unavailable'
  const event = deferredPrompt
  deferredPrompt = null
  emit()
  event.prompt()
  const { outcome } = await event.userChoice
  if (outcome === 'accepted') markInstalled()
  return outcome
}

/** Chrome на Android умеет сказать, что это приложение уже стоит на телефоне. */
export async function detectInstalledApp() {
  try {
    const apps = (await navigator.getInstalledRelatedApps?.()) || []
    if (apps.length) markInstalled()
    return apps.length > 0
  } catch {
    return false
  }
}

export function detectPlatform() {
  const ua = navigator.userAgent
  const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  const android = /Android/i.test(ua)
  let browser = 'other'
  if (/YaBrowser/i.test(ua)) browser = 'yandex'
  else if (/SamsungBrowser/i.test(ua)) browser = 'samsung'
  else if (/EdgiOS|EdgA|Edg\//i.test(ua)) browser = 'edge'
  else if (/FxiOS|Firefox/i.test(ua)) browser = 'firefox'
  else if (/CriOS|Chrome/i.test(ua)) browser = 'chrome'
  else if (/Safari/i.test(ua)) browser = 'safari'
  const os = ios ? 'ios' : android ? 'android' : 'desktop'
  return { os, browser, mobile: ios || android }
}

// ---------- Обновления ----------

export function hasUpdate() {
  return Boolean(waitingWorker)
}

export function applyUpdate() {
  waitingWorker?.postMessage({ type: 'SKIP_WAITING' })
}

export function registerServiceWorker() {
  // В разработке (vite dev) service worker мешал бы горячей перезагрузке.
  if (!import.meta.env.PROD || !('serviceWorker' in navigator) || !window.isSecureContext) return
  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
      const track = (worker) => {
        worker?.addEventListener('statechange', () => {
          if (worker.state === 'installed' && navigator.serviceWorker.controller) {
            waitingWorker = worker
            emit()
          }
        })
      }
      if (registration.waiting && navigator.serviceWorker.controller) {
        waitingWorker = registration.waiting
        emit()
      }
      registration.addEventListener('updatefound', () => track(registration.installing))
      // Приложение открыто днями — раз в час проверяем, не вышла ли новая версия.
      setInterval(() => registration.update().catch(() => {}), 60 * 60 * 1000)
    } catch {
      /* без service worker приложение просто работает онлайн */
    }
  })
  let reloading = false
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloading) return
    reloading = true
    window.location.reload()
  })
}
