import { createPortal } from 'react-dom'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useDialogFocus } from '../components/Modal'
import {
  IconAuto,
  IconBolt,
  IconCar,
  IconChevron,
  IconClose,
  IconDownload,
  IconHelp,
  IconLogout,
  IconMoon,
  IconShield,
  IconSpark,
  IconSun,
  IconUser,
} from '../components/icons'
import { useInstall } from '../pwa/InstallProvider'
import { useTheme } from '../theme/ThemeProvider'
import { Avatar, LEVEL_SHORT } from './TopBar'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const ADMIN_URL = API_BASE.replace(/\/api\/?$/, '/admin/')
const THEMES = [
  ['auto', 'Авто', IconAuto],
  ['night', 'Ночь', IconMoon],
  ['day', 'День', IconSun],
]

/** Меню «Ещё»: профиль, тема, установка приложения, обучалка, выход. */
export default function MoreSheet({ onClose }) {
  const ref = useDialogFocus(onClose)
  const navigate = useNavigate()
  const { isAuthenticated, isAdmin, user, logout } = useAuth()
  const { mode, setMode } = useTheme()
  const { offerInstall, install, standalone, updateAvailable, applyUpdate } = useInstall()
  const level = user?.access?.level ?? 0

  const go = (path) => {
    onClose()
    navigate(path)
  }

  return createPortal(
    <div className="sheet-backdrop" onClick={onClose}>
      <div
        ref={ref}
        tabIndex={-1}
        className="more"
        role="dialog"
        aria-modal="true"
        aria-label="Меню"
        onClick={(event) => event.stopPropagation()}
      >
        <span className="more__grabber" />
        <button type="button" className="sheet__close more__close" onClick={onClose} aria-label="Закрыть">
          <IconClose width={16} height={16} />
        </button>

        {isAuthenticated ? (
          <button type="button" className="more__me" onClick={() => go('/profile')}>
            <Avatar user={user} />
            <span>
              <b>{user.full_name || user.username}</b>
              <small className={`level-text level-${level}`}>
                {user.access?.level_display || LEVEL_SHORT[level]}
              </small>
            </span>
            <IconChevron width={18} height={18} />
          </button>
        ) : (
          <div className="more__guest">
            <h2 className="display drip">Погнали?</h2>
            <p className="muted">Войдите, чтобы бронировать машины и смотреть поездки.</p>
            <div className="more__row">
              <Link to="/register" className="btn btn--cta" onClick={onClose}>
                Регистрация
              </Link>
              <Link to="/login" className="btn btn--ghost" onClick={onClose}>
                Вход
              </Link>
            </div>
          </div>
        )}

        {updateAvailable && (
          <button type="button" className="more__update" onClick={applyUpdate}>
            <IconSpark width={18} height={18} />
            Доступна новая версия — обновить
          </button>
        )}

        {offerInstall && (
          <button type="button" className="more__install" onClick={install}>
            <img src="/icons/icon-96.png" alt="" />
            <span>
              <b>Установить приложение</b>
              <small>Иконка на главном экране, запуск без браузера</small>
            </span>
            <IconDownload width={20} height={20} />
          </button>
        )}

        <ul className="more__list">
          {isAuthenticated && (
            <li>
              <button type="button" onClick={() => go('/profile')}>
                <IconCar />
                Мои поездки
                <IconChevron width={16} height={16} />
              </button>
            </li>
          )}
          <li>
            <button type="button" onClick={() => go('/verification')}>
              <IconShield />
              Рули ID — проверка водителя
              <IconChevron width={16} height={16} />
            </button>
          </li>
          {isAuthenticated && (
            <li>
              <button type="button" onClick={() => go('/profile#settings')}>
                <IconUser />
                Телефон и данные
                <IconChevron width={16} height={16} />
              </button>
            </li>
          )}
          <li>
            <button type="button" onClick={() => go('/help')}>
              <IconHelp />
              Обучение и помощь
              <IconChevron width={16} height={16} />
            </button>
          </li>
          <li>
            <button type="button" onClick={() => go('/rewards')}>
              <IconBolt />
              Движ: баллы и рейтинг
              <IconChevron width={16} height={16} />
            </button>
          </li>
          {isAdmin && (
            <li>
              <a href={ADMIN_URL} target="_blank" rel="noreferrer">
                <IconSpark />
                Панель модератора
                <IconChevron width={16} height={16} />
              </a>
            </li>
          )}
        </ul>

        <div className="more__theme">
          <span>Тема</span>
          <div className="segmented">
            {THEMES.map(([value, label, Icon]) => (
              <button
                key={value}
                type="button"
                className={mode === value ? 'is-active' : ''}
                aria-pressed={mode === value}
                onClick={() => setMode(value)}
              >
                <Icon width={15} height={15} />
                {label}
              </button>
            ))}
          </div>
        </div>

        {isAuthenticated && (
          <button
            type="button"
            className="more__logout"
            onClick={() => {
              logout()
              go('/')
            }}
          >
            <IconLogout width={18} height={18} />
            Выйти
          </button>
        )}
        <p className="more__foot">
          Рули · Минск · {standalone ? 'приложение' : 'веб-версия'}
        </p>
      </div>
    </div>,
    document.body,
  )
}
