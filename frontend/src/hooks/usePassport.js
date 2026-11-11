import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export function usePassport(carId, enabled = true) {
  return useQuery({
    queryKey: ['passport', carId],
    queryFn: async () => (await api.get(`/cars/${carId}/passport/`)).data,
    enabled: Boolean(carId) && enabled,
    staleTime: 30_000,
  })
}

export function useVerifyChain(carId) {
  return useMutation({
    mutationFn: async () => (await api.get(`/cars/${carId}/passport/verify/`)).data,
  })
}

/** Акт осмотра: фото ракурсов, отметки повреждений, чистота. */
export function useSubmitInspection(rentalId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ kind, photos, damages, cleanliness, confirmed, location }) => {
      const form = new FormData()
      form.append('kind', kind)
      Object.entries(photos).forEach(([angle, file]) => form.append(angle, file))
      form.append('damages', JSON.stringify(damages))
      if (cleanliness) form.append('cleanliness', String(cleanliness))
      form.append('confirmed', confirmed ? 'true' : 'false')
      if (location) {
        form.append('lat', String(location.lat))
        form.append('lng', String(location.lng))
      }
      return (await api.post(`/rentals/${rentalId}/inspections/`, form)).data
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['rental', 'current'], data.rental)
      queryClient.invalidateQueries({ queryKey: ['passport'] })
      queryClient.invalidateQueries({ queryKey: ['rentals'] })
    },
  })
}
