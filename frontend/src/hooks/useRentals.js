import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function useCurrentRental() {
  const { isAuthenticated } = useAuth()

  return useQuery({
    queryKey: ['rental', 'current'],
    queryFn: async () => {
      const { data } = await api.get('/rentals/current/')
      return data
    },
    enabled: isAuthenticated,
  })
}

export function useRentalHistory() {
  const { isAuthenticated } = useAuth()

  return useQuery({
    queryKey: ['rentals'],
    queryFn: async () => {
      const { data } = await api.get('/rentals/', { params: { page_size: 100 } })
      return data.results
    },
    enabled: isAuthenticated,
  })
}

function useRentalMutation(mutationFn) {
  const queryClient = useQueryClient()
  const { refreshUser } = useAuth()

  return useMutation({
    mutationFn,
    onSuccess: async () => {
      ;['rentals', 'cars', 'car', 'passport', 'verification', 'rewards', 'leaderboard'].forEach((key) =>
        queryClient.invalidateQueries({ queryKey: [key] }),
      )
      // Поездка без замечаний может поднять уровень «Рули ID» — обновляем профиль в шапке.
      refreshUser().catch(() => {})
      // Ждём свежую бронь: иначе кнопки виджета на миг снова активны со старым статусом.
      await queryClient.invalidateQueries({ queryKey: ['rental', 'current'] })
    },
  })
}

/** Бронь с координатами клиента — по ним считается честное бесплатное ожидание. */
export const useBookCar = () =>
  useRentalMutation(({ carId, location }) =>
    api.post('/rentals/', {
      car: carId,
      ...(location ? { lat: location.lat, lng: location.lng } : {}),
    }),
  )

export const useCarMissing = () =>
  useRentalMutation(({ rentalId, location }) =>
    api.post(`/rentals/${rentalId}/car-missing/`, { lat: location.lat, lng: location.lng }),
  )

export const useStartRental = () =>
  useRentalMutation((rentalId) => api.post(`/rentals/${rentalId}/start/`))

/** Завершить поездку; usePoints — оплатить баллами «Движа» до 30% стоимости. */
export const useFinishRental = () =>
  useRentalMutation(({ rentalId, usePoints = false }) =>
    api.post(`/rentals/${rentalId}/finish/`, { use_points: usePoints }),
  )

export const useCancelRental = () =>
  useRentalMutation((rentalId) => api.post(`/rentals/${rentalId}/cancel/`))
