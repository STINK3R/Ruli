import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { IconBolt, IconCar, IconMap, IconMore, IconShield } from '../components/icons'
import { useCurrentRental } from '../hooks/useRentals'

/** Нижние вкладки на телефоне — как в настоящем приложении. */
export default function TabBar({ onMore, moreOpen }) {
  const { isAuthenticated } = useAuth()
  const { data: rental } = useCurrentRental()
  const tab = ({ isActive }) => `tabbar__item ${isActive && !moreOpen ? 'is-active' : ''}`

  return (
    <nav className="tabbar" aria-label="Разделы">
      <NavLink to="/" end className={tab}>
        <IconMap />
        <span>Карта</span>
        {rental && <i className="tabbar__dot" aria-label="Есть бронь" />}
      </NavLink>
      <NavLink to={isAuthenticated ? '/profile' : '/login'} className={tab}>
        <IconCar />
        <span>Поездки</span>
      </NavLink>
      <NavLink to="/rewards" className={tab}>
        <IconBolt />
        <span>Движ</span>
      </NavLink>
      <NavLink to="/verification" className={tab}>
        <IconShield />
        <span>Рули ID</span>
      </NavLink>
      <button type="button" className={`tabbar__item ${moreOpen ? 'is-active' : ''}`} onClick={onMore}>
        <IconMore />
        <span>Ещё</span>
      </button>
    </nav>
  )
}
