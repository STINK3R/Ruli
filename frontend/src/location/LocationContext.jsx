import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

const MINSK_CENTER = { lat: 53.9023, lng: 27.5619 }
const SERVICE_RADIUS_M = 40_000

// Если геолокация недоступна или клиент далеко от Минска (например, на защите
// курсовой в другом городе), расстояния считаются от этой точки.
export const DEMO_LOCATION = { lat: 53.90866, lng: 27.57516, label: 'площадь Победы', source: 'demo' }

function distanceM(a, b) {
  const rad = Math.PI / 180
  const dLat = (b.lat - a.lat) * rad
  const dLng = (b.lng - a.lng) * rad
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h))
}

const LocationContext = createContext(null)

export function LocationProvider({ children }) {
  const [location, setLocation] = useState(DEMO_LOCATION)
  const [locating, setLocating] = useState(false)
  const locationRef = useRef(DEMO_LOCATION)
  locationRef.current = location

  /**
   * Запрашивает геолокацию; результат: { location, reason } — reason объясняет, почему точка не GPS.
   * Стартовый запрос (initial) не затирает точку, которую клиент уже отметил на карте сам.
   */
  const locate = useCallback(
    ({ initial = false } = {}) =>
      new Promise((resolve) => {
        const keepManual = (next) =>
          setLocation((prev) => (initial && prev.source === 'manual' ? prev : next))
        // Без доступа к GPS остаёмся там, где клиент сейчас (демо-точка или отмеченная).
        const fallback = (reason) => {
          const current = locationRef.current
          resolve({ location: current, reason: current.source === 'manual' ? `${reason}_manual` : reason })
        }

        if (!navigator.geolocation) {
          fallback('unsupported')
          return
        }
        setLocating(true)
        navigator.geolocation.getCurrentPosition(
          ({ coords }) => {
            setLocating(false)
            const point = { lat: coords.latitude, lng: coords.longitude }
            if (distanceM(point, MINSK_CENTER) > SERVICE_RADIUS_M) {
              if (locationRef.current.source === 'manual') {
                fallback('far')
              } else {
                keepManual(DEMO_LOCATION)
                resolve({ location: DEMO_LOCATION, reason: 'far' })
              }
              return
            }
            const next = { ...point, label: 'Вы здесь', source: 'gps' }
            keepManual(next)
            resolve({ location: next, reason: null })
          },
          () => {
            setLocating(false)
            fallback('denied')
          },
          { enableHighAccuracy: true, timeout: 8000, maximumAge: 60_000 },
        )
      }),
    [],
  )

  const setManualLocation = useCallback((lat, lng) => {
    setLocation({ lat, lng, label: 'Отмечено на карте', source: 'manual' })
  }, [])

  useEffect(() => {
    locate({ initial: true })
  }, [locate])

  const value = useMemo(
    () => ({ location, locating, locate, setManualLocation }),
    [location, locating, locate, setManualLocation],
  )

  return <LocationContext.Provider value={value}>{children}</LocationContext.Provider>
}

export function useUserLocation() {
  const context = useContext(LocationContext)
  if (!context) throw new Error('useUserLocation используется вне LocationProvider')
  return context
}

export const LOCATION_HINTS = {
  unsupported: 'Браузер не поддерживает геолокацию — расстояния считаются от площади Победы.',
  denied: 'Нет доступа к геолокации — расстояния считаются от площади Победы.',
  far: 'Вы далеко от Минска — расстояния считаются от площади Победы.',
  unsupported_manual: 'Браузер не поддерживает геолокацию — расстояния считаются от отмеченной точки.',
  denied_manual: 'Нет доступа к геолокации — расстояния считаются от отмеченной точки.',
  far_manual: 'Вы далеко от Минска — расстояния считаются от отмеченной точки.',
}
