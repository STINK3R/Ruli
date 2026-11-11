import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const ACCESS_KEY = 'carsharing_access'
const REFRESH_KEY = 'carsharing_refresh'

export const tokens = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  save: (access, refresh) => {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use((config) => {
  const access = tokens.getAccess()
  if (access) config.headers.Authorization = `Bearer ${access}`
  return config
})

let refreshRequest = null

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const refresh = tokens.getRefresh()

    if (error.response?.status !== 401 || original._retried || !refresh) {
      return Promise.reject(error)
    }

    original._retried = true
    // Одновременные 401 не должны порождать несколько запросов на обновление токена.
    refreshRequest =
      refreshRequest ||
      axios
        .post(`${BASE_URL}/auth/token/refresh/`, { refresh })
        .finally(() => {
          refreshRequest = null
        })

    try {
      const { data } = await refreshRequest
      tokens.save(data.access, data.refresh)
      original.headers.Authorization = `Bearer ${data.access}`
      return api(original)
    } catch (refreshError) {
      // Сервер перезапускается или нет сети — сессию не трогаем, просто показываем ошибку.
      const status = refreshError?.response?.status
      if (!status || status >= 500) return Promise.reject(error)
      // Сессия истекла: повторяем запрос анонимно — публичные страницы продолжают работать,
      // а на закрытые ProtectedRoute сам отправит ко входу. _retried не даст зациклиться.
      tokens.clear()
      delete original.headers.Authorization
      return api(original)
    }
  },
)

const first = (value) => (Array.isArray(value) ? value[0] : value)

/** Машинный код ошибки DRF: в ValidationError он приходит списком. */
export function errorCode(error) {
  return first(error?.response?.data?.code) || null
}

export function extractError(error, fallback = 'Что-то пошло не так') {
  const status = error?.response?.status
  const data = error?.response?.data
  if (status === 413) return 'Фото слишком большие — переснимите или уменьшите их.'
  if (status === 429) return 'Слишком много попыток — попробуйте чуть позже.'
  // HTML-страница ошибки от nginx (502, 504) — не показываем её разметку.
  if (!data || (typeof data === 'string' && /^\s*</.test(data))) {
    if (!error?.response) return 'Нет связи с сервером — проверьте интернет.'
    return status >= 500 ? 'Сервер недоступен, попробуйте ещё раз.' : fallback
  }
  if (typeof data === 'string') return data
  if (data.detail) return String(first(data.detail))
  const firstKey = Object.keys(data)[0]
  if (!firstKey) return fallback
  return String(first(data[firstKey]))
}
