import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const ADMIN_URL = API_BASE.replace(/\/api\/?$/, '/admin/')

const LEVEL_SHORT = ['Гость', 'Проверка', 'Водитель', 'Плюс']

export default function Navbar() {
  const { isAuthenticated, isAdmin, user, logout } = useAuth()
  const navigate = useNavigate()

  const linkClass = ({ isActive }) =>
    isActive ? 'navbar__link navbar__link--active' : 'navbar__link'

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const initials = user
    ? `${user.last_name?.[0] || user.username[0]}${user.first_name?.[0] || ''}`.toUpperCase()
    : ''
  const level = user?.access?.level ?? 0

  return (
    <header className="navbar">
      <div className="navbar__inner">
        <NavLink to="/" className="navbar__logo">
          <span className="monogram">Р</span>
          <span className="navbar__logo-text">Рули</span>
        </NavLink>

        <nav className="navbar__links">
          <NavLink to="/" className={(state) => `${linkClass(state)} navbar__link--wide`} end>
            Карта
          </NavLink>

          {isAuthenticated && (
            <NavLink to="/profile" className={linkClass}>
              <span className="navbar__label-full">Мои поездки</span>
              <span className="navbar__label-short">Поездки</span>
            </NavLink>
          )}

          {isAdmin && (
            <a
              href={ADMIN_URL}
              target="_blank"
              rel="noreferrer"
              className="navbar__link navbar__link--wide"
            >
              Админка
            </a>
          )}

          {isAuthenticated ? (
            <>
              <Link
                to={level < 2 ? '/verification' : '/profile'}
                className="navbar__user"
                title={user.access?.level_display}
              >
                <span className={`navbar__avatar level-${level}`}>{initials}</span>
                <span className="navbar__who">
                  <span className="navbar__name">{user.full_name || user.username}</span>
                  <span className={`navbar__level level-${level}`}>{LEVEL_SHORT[level]}</span>
                </span>
              </Link>
              <button className="btn btn--ghost" onClick={handleLogout}>
                Выйти
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className={linkClass}>
                Вход
              </NavLink>
              <NavLink to="/register" className="btn btn--dark">
                Регистрация
              </NavLink>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
