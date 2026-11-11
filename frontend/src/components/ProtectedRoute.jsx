import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  const { pathname } = useLocation()

  if (loading) return <div className="state">Загрузка…</div>
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: pathname }} />
  return children
}
