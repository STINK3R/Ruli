import { useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api, tokens } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(tokens.getAccess()))

  useEffect(() => {
    if (!tokens.getAccess()) return
    api
      .get('/auth/me/')
      .then(({ data }) => setUser(data))
      .catch((error) => {
        // Токены стираем только при отказе в доступе: 502 во время перезапуска бэкенда
        // не должен разлогинивать — после перезагрузки страницы сессия восстановится.
        if ([401, 403].includes(error.response?.status)) tokens.clear()
      })
      .finally(() => setLoading(false))
  }, [])

  const value = useMemo(() => {
    // Кэш запросов привязан к человеку: бронь, поездки и анкета не должны
    // пережить выход или достаться следующему вошедшему.
    const startSession = (me) => {
      queryClient.clear()
      setUser(me)
    }

    return {
      user,
      loading,
      isAuthenticated: Boolean(user),
      isAdmin: Boolean(user?.is_staff),
      async login(username, password) {
        const { data } = await api.post('/auth/token/', { username, password })
        tokens.save(data.access, data.refresh)
        const me = await api.get('/auth/me/')
        startSession(me.data)
      },
      async register(payload) {
        const { data } = await api.post('/auth/register/', payload)
        tokens.save(data.access, data.refresh)
        startSession(data.user)
      },
      async refreshUser() {
        if (!tokens.getAccess()) return null
        const { data } = await api.get('/auth/me/')
        setUser(data)
        return data
      },
      async updateProfile(payload) {
        const { data } = await api.patch('/auth/me/', payload)
        setUser(data)
        return data
      },
      logout() {
        tokens.clear()
        queryClient.clear()
        setUser(null)
      },
    }
  }, [user, loading, queryClient])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth используется вне AuthProvider')
  return context
}
