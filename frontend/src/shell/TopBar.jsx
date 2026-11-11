import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { IconAuto, IconDownload, IconMoon, IconSun } from '../components/icons'
import { useInstall } from '../pwa/InstallProvider'
import { MODE_LABELS, useTheme } from '../theme/ThemeProvider'

export const LEVEL_SHORT = ['Гость', 'Проверка', 'Водитель', 'Плюс']
const THEME_ICONS = { auto: IconAuto, night: IconMoon, day: IconSun }

export function initialsOf(user) {
  if (!user) return ''
  return `${user.last_name?.[0] || user.username[0]}${user.first_name?.[0] || ''}`.toUpperCase()
}

export function Logo({ compact = false }) {
  return (
    <Link to="/" className="logo" aria-label="Рули — на карту">
      <img src="/icons/icon-96.png" alt="" className="logo__icon" />
      {!compact && <span className="logo__word">Рули</span>}
    </Link>
  )
}

export function ThemeButton() {
  const { mode, cycle } = useTheme()
  const Icon = THEME_ICONS[mode]
  return (
    <button type="button" className="icon-btn" onClick={cycle} title={`Тема: ${MODE_LABELS[mode]}`}>
      <Icon width={18} height={18} />
    </button>
  )
}

export function Avatar({ user, onClick }) {
  const level = user?.access?.level ?? 0
  const props = { className: `avatar level-${level}`, title: user?.access?.level_display }
  return onClick ? (
    <button type="button" {...props} onClick={onClick}>
      {initialsOf(user)}
    </button>
  ) : (
    <span {...props}>{initialsOf(user)}</span>
  )
}

/** Верхняя панель. На карте — прозрачная поверх, на остальных экранах — плашка. */
export default function TopBar({ onMenu, overMap = false }) {
  const { isAuthenticated, user } = useAuth()
  const { offerInstall, install } = useInstall()
  const link = ({ isActive }) => `topbar__link ${isActive ? 'is-active' : ''}`

  return (
    <header className={`topbar ${overMap ? 'topbar--map' : ''}`}>
      <Logo />
      <nav className="topbar__nav">
        <NavLink to="/" end className={link}>
          Карта
        </NavLink>
        {isAuthenticated && (
          <NavLink to="/profile" className={link}>
            Поездки
          </NavLink>
        )}
        <NavLink to="/rewards" className={link}>
          Движ
        </NavLink>
        <NavLink to="/verification" className={link}>
          Рули ID
        </NavLink>
      </nav>
      <div className="topbar__actions">
        {offerInstall && (
          <button type="button" className="btn btn--soft btn--sm topbar__install" onClick={install}>
            <IconDownload width={16} height={16} />
            Установить
          </button>
        )}
        <ThemeButton />
        {isAuthenticated ? (
          <button type="button" className="topbar__user" onClick={onMenu}>
            <span className="topbar__who">
              <b>{user.first_name || user.username}</b>
              <small className={`level-text level-${user.access?.level ?? 0}`}>
                {LEVEL_SHORT[user.access?.level ?? 0]}
              </small>
            </span>
            <Avatar user={user} />
          </button>
        ) : (
          <>
            <NavLink to="/login" className="topbar__link topbar__login">
              Вход
            </NavLink>
            <NavLink to="/register" className="btn btn--cta btn--sm topbar__signup">
              Регистрация
            </NavLink>
          </>
        )}
      </div>
    </header>
  )
}
