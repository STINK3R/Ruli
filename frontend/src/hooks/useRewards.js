import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function useRewards() {
  const { isAuthenticated } = useAuth()
  return useQuery({
    queryKey: ['rewards'],
    queryFn: async () => (await api.get('/rewards/')).data,
    enabled: isAuthenticated,
  })
}

export function useRewardsHistory(enabled = true) {
  const { isAuthenticated } = useAuth()
  return useQuery({
    queryKey: ['rewards', 'history'],
    queryFn: async () => (await api.get('/rewards/history/')).data,
    enabled: isAuthenticated && enabled,
  })
}

export function useLeaderboard(period) {
  return useQuery({
    queryKey: ['leaderboard', period],
    queryFn: async () => (await api.get('/rewards/leaderboard/', { params: { period } })).data,
    staleTime: 30_000,
  })
}
