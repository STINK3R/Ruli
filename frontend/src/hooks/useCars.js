import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

// Четыре знака после запятой ≈ 11 м: мелкие колебания GPS не плодят запросы.
const round = (value) => Math.round(value * 1e4) / 1e4

export function useCars(filters = {}, location = null) {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== '' && value != null),
  )
  if (location) {
    params.lat = round(location.lat)
    params.lng = round(location.lng)
  }

  return useQuery({
    queryKey: ['cars', params],
    queryFn: async () => {
      const { data } = await api.get('/cars/', { params: { ...params, page_size: 100 } })
      return data.results
    },
    placeholderData: keepPreviousData,
  })
}

export function useCar(id) {
  return useQuery({
    queryKey: ['car', id],
    queryFn: async () => {
      const { data } = await api.get(`/cars/${id}/`)
      return data
    },
    enabled: Boolean(id),
  })
}

export function useWalkRoute(carId, location) {
  const lat = location ? round(location.lat) : null
  const lng = location ? round(location.lng) : null

  return useQuery({
    queryKey: ['route', carId, lat, lng],
    queryFn: async () => {
      const { data } = await api.get(`/cars/${carId}/route/`, { params: { lat, lng } })
      return data
    },
    enabled: Boolean(carId && location),
    staleTime: 60_000,
    retry: 0,
  })
}
