import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function useVerification() {
  const { isAuthenticated, user, refreshUser } = useAuth()
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['verification'],
    queryFn: async () => (await api.get('/verification/')).data,
    enabled: isAuthenticated,
    // Вернулись из вкладки админки — сразу видно решение модератора, без ожидания опроса.
    refetchOnWindowFocus: true,
    // Пока заявка на проверке, статус подтягивается сам — модератор может решить в любой момент.
    refetchInterval: (query) =>
      query.state.data?.verification?.status === 'pending' ? 15_000 : false,
  })

  // Решение модератора приходит через опрос заявки — подтягиваем уровень и в шапку, и в каталог.
  const level = query.data?.access?.level
  const status = query.data?.access?.status
  useEffect(() => {
    if (level == null || !user?.access) return
    if (level !== user.access.level || status !== user.access.status) {
      refreshUser().catch(() => {})
      queryClient.invalidateQueries({ queryKey: ['cars'] })
    }
  }, [level, status])

  return query
}

export function useRequirements() {
  return useQuery({
    queryKey: ['requirements'],
    queryFn: async () => (await api.get('/verification/requirements/')).data,
    staleTime: 5 * 60_000,
  })
}

function useVerificationMutation(mutationFn) {
  const queryClient = useQueryClient()
  const { refreshUser } = useAuth()
  return useMutation({
    mutationFn,
    onSuccess: (data) => {
      queryClient.setQueryData(['verification'], data)
      queryClient.invalidateQueries({ queryKey: ['cars'] })
      refreshUser()
    },
  })
}

export const useStartVerification = () =>
  useVerificationMutation(async () => (await api.post('/verification/')).data)

export const useSaveVerification = () =>
  useVerificationMutation(async (fields) => (await api.patch('/verification/', fields)).data)

export const useUploadDocument = () =>
  useVerificationMutation(async ({ kind, file, demo = false }) => {
    const form = new FormData()
    form.append('file', file, `${kind}.jpg`)
    if (demo) form.append('demo', '1')
    return (await api.put(`/verification/documents/${kind}/`, form)).data
  })

/** Кадры проверки «живости» одной формой: имя поля — код движения. */
function framesForm(frames, demo, extra = {}) {
  const form = new FormData()
  Object.entries(frames).forEach(([code, blob]) => form.append(code, blob, `${code}.jpg`))
  if (demo) form.append('demo', '1')
  Object.entries(extra).forEach(([key, value]) => form.append(key, value))
  return form
}

export const startLiveness = async () => (await api.post('/verification/liveness/')).data

export const submitLiveness = async (check, frames, demo) =>
  (await api.post(`/verification/liveness/${check.id}/`, framesForm(frames, demo))).data

export const startTripFaceCheck = async (rentalId) => (await api.post(`/rentals/${rentalId}/face-check/start/`)).data

export const submitTripFaceCheck = async (rentalId, check, frames, demo) =>
  (await api.post(`/rentals/${rentalId}/face-check/`, framesForm(frames, demo, { check: check.id }))).data

export const fetchDemoProfile = async () => (await api.get('/verification/demo-profile/')).data

export function useSendPhoneCode() {
  return useMutation({ mutationFn: async () => (await api.post('/auth/phone/send/')).data })
}

export function useConfirmPhone() {
  const queryClient = useQueryClient()
  const { refreshUser } = useAuth()
  return useMutation({
    mutationFn: async (code) => (await api.post('/auth/phone/confirm/', { code })).data,
    onSuccess: () => {
      refreshUser()
      queryClient.invalidateQueries({ queryKey: ['verification'] })
      queryClient.invalidateQueries({ queryKey: ['cars'] })
    },
  })
}

export const useSubmitVerification = () =>
  useVerificationMutation(async () => (await api.post('/verification/submit/')).data)

export const useWithdrawConsent = () =>
  useVerificationMutation(async () => (await api.post('/verification/consent/withdraw/')).data)

/** Своё фото документа — грузится с токеном как blob и показывается через object URL. */
export async function fetchDocumentPreview(kind) {
  const { data } = await api.get(`/verification/documents/${kind}/`, { responseType: 'blob' })
  return URL.createObjectURL(data)
}
