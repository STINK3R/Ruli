import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../api/client'

const round = (value) => Math.round(value * 1e4) / 1e4

export function useDebounced(value, delay = 350) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

/** Подсказки адресов по Минску (Nominatim через наш бэкенд). */
export function useAddressSearch(query) {
  const q = useDebounced(query.trim())
  return useQuery({
    queryKey: ['geocode', q],
    queryFn: async () => (await api.get('/geocode/', { params: { q } })).data,
    enabled: q.length >= 3,
    staleTime: 10 * 60_000,
    placeholderData: keepPreviousData,
  })
}

export async function reverseGeocode(lat, lng) {
  try {
    return (await api.get('/geocode/', { params: { lat: round(lat), lng: round(lng) } })).data
  } catch {
    return { title: 'Точка на карте', subtitle: '', lat, lng }
  }
}

/** Полная цена поездки до точки для ближайших машин. */
export function useTripPlan(origin, destination) {
  const params = destination && origin
    ? { lat: round(origin.lat), lng: round(origin.lng), to_lat: round(destination.lat), to_lng: round(destination.lng) }
    : null
  return useQuery({
    queryKey: ['plan', params],
    queryFn: async () => (await api.get('/cars/plan/', { params })).data,
    enabled: Boolean(params),
    staleTime: 60_000,
    retry: 0,
  })
}
