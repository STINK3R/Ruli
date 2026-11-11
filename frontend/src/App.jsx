import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import { useIsMobile } from './hooks/useMediaQuery'
import CarDetailPage from './pages/CarDetailPage'
import CatalogPage from './pages/CatalogPage'
import HelpPage from './pages/HelpPage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import RegisterPage from './pages/RegisterPage'
import RewardsPage from './pages/RewardsPage'
import VerificationPage from './pages/VerificationPage'
import MoreSheet from './shell/MoreSheet'
import TabBar from './shell/TabBar'
import TopBar from './shell/TopBar'

const AUTH_ROUTES = ['/login', '/register']

export default function App() {
  const { pathname } = useLocation()
  const mobile = useIsMobile()
  const [moreOpen, setMoreOpen] = useState(false)
  const onMap = pathname === '/'
  const onAuth = AUTH_ROUTES.includes(pathname)

  // Новая страница — сверху и без открытого меню.
  useEffect(() => {
    setMoreOpen(false)
    if (!onMap) window.scrollTo(0, 0)
  }, [pathname, onMap])

  useEffect(() => {
    document.body.classList.toggle('on-map', onMap)
  }, [onMap])

  const openMenu = () => setMoreOpen(true)

  return (
    <>
      {/* На телефоне над картой — своя строка поиска, верхняя панель не нужна. */}
      {!(mobile && onMap) && <TopBar onMenu={openMenu} overMap={onMap} />}

      <Routes>
        <Route path="/" element={<CatalogPage onMenu={openMenu} />} />
        <Route
          path="*"
          element={
            <main className={`container ${onAuth ? 'container--auth' : ''}`}>
              <Routes>
                <Route path="/cars/:id" element={<CarDetailPage />} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
                <Route path="/rewards" element={<RewardsPage />} />
                <Route path="/help" element={<HelpPage />} />
                <Route
                  path="/profile"
                  element={
                    <ProtectedRoute>
                      <ProfilePage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/verification"
                  element={
                    <ProtectedRoute>
                      <VerificationPage />
                    </ProtectedRoute>
                  }
                />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
          }
        />
      </Routes>

      {mobile && !onAuth && <TabBar onMore={() => setMoreOpen((open) => !open)} moreOpen={moreOpen} />}
      {moreOpen && <MoreSheet onClose={() => setMoreOpen(false)} />}
    </>
  )
}
