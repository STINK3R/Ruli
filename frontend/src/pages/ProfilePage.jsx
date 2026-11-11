import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { extractError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import PhoneVerify from '../components/PhoneVerify'
import RentalStatusWidget from '../components/RentalStatusWidget'
import RuliIdCard from '../components/RuliId'
import { IconClock, IconDownload, IconRoute, IconSeal, IconShield } from '../components/icons'
import { useRentalHistory } from '../hooks/useRentals'
import { useInstall } from '../pwa/InstallProvider'
import { useUi } from '../ui/UiProvider'
import { carTopViewSvg, formatMoney, isCutout } from '../utils/carVisual'

const formatDate = (value) =>
  new Date(value).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })

const EDITABLE = [
  { name: 'email', label: 'Email', type: 'email' },
  { name: 'phone_number', label: 'Телефон' },
]

function ProfileForm() {
  const { user, updateProfile } = useAuth()
  const { notify } = useUi()
  const [form, setForm] = useState(() =>
    Object.fromEntries(EDITABLE.map(({ name }) => [name, user[name] || ''])),
  )
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setPending(true)
    try {
      await updateProfile(form)
      notify('Контакты сохранены')
    } catch (err) {
      setError(extractError(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <form className="card profile-card" id="settings" onSubmit={handleSubmit}>
      <div className="profile-card__head">
        <span className={`profile-card__avatar level-${user.access?.level ?? 0}`}>
          {(user.last_name?.[0] || user.username[0]).toUpperCase()}
          {(user.first_name?.[0] || '').toUpperCase()}
        </span>
        <div>
          <h3>{user.full_name || user.username}</h3>
          <span className="muted">{user.username}</span>
        </div>
      </div>

      {EDITABLE.map(({ name, label, type = 'text' }) => (
        <div className="field" key={name}>
          <label htmlFor={`profile-${name}`}>{label}</label>
          <input
            id={`profile-${name}`}
            type={type}
            value={form[name]}
            onChange={(event) => setForm({ ...form, [name]: event.target.value })}
          />
        </div>
      ))}

      {user.driver_license_number && (
        <div className="readonly-list">
          <div>
            <span>Права</span>
            <b>{user.driver_license_number}</b>
          </div>
          {user.license_expires_on && (
            <div>
              <span>Действуют до</span>
              <b>{new Date(user.license_expires_on).toLocaleDateString('ru-RU')}</b>
            </div>
          )}
          <p className="fine-print">Данные прав меняются только через проверку «Рули ID».</p>
        </div>
      )}

      {error && <p className="error-text">{error}</p>}

      <button className="btn btn--dark btn--block" disabled={pending}>
        {pending ? 'Сохраняем…' : 'Сохранить контакты'}
      </button>

      <div className="profile-card__phone">
        <h3>Подтверждение телефона</h3>
        <p className="fine-print">Новый номер снова подтверждается кодом — до этого бронь закрыта.</p>
        <PhoneVerify />
      </div>
    </form>
  )
}

function InstallCard() {
  const { offerInstall, install } = useInstall()
  if (!offerInstall) return null
  return (
    <button type="button" className="install-card" onClick={install}>
      <img src="/icons/icon-192.png" alt="" />
      <span>
        <b>Рули на главный экран</b>
        <small>Запуск в одно касание, без адресной строки</small>
      </span>
      <IconDownload width={22} height={22} />
    </button>
  )
}

function TripItem({ rental, index }) {
  const waiting = Number(rental.waiting_cost || 0)

  return (
    <div className="trip" style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}>
      <div className={`trip__photo ${isCutout(rental.car.image) ? 'studio' : ''}`}>
        {rental.car.image ? (
          <img src={rental.car.image} alt="" loading="lazy" />
        ) : (
          <span dangerouslySetInnerHTML={{ __html: carTopViewSvg(rental.car, { width: 22 }) }} />
        )}
      </div>

      <div className="trip__main">
        <div className="trip__title">
          {rental.car.title}
          <span className="muted"> · {rental.car.license_plate}</span>
        </div>
        <div className="trip__meta">
          <span className="trip__date">{formatDate(rental.reserved_at)}</span>
          <span className={`badge badge--${rental.status}`}>{rental.status_display}</span>
          {rental.cancel_reason === 'car_missing' && <span className="badge">Машины не было</span>}
          {rental.inspections.map((inspection) => (
            <span key={inspection.id} className="seal-chip" title={inspection.seal_hash}>
              <IconSeal width={11} height={11} />#{inspection.seal_short}
            </span>
          ))}
        </div>
      </div>

      <div className="trip__numbers">
        <div className="trip__cost">
          {rental.total_cost != null ? formatMoney(rental.total_cost) : '—'}
        </div>
        <div className="muted">
          {rental.duration_minutes != null ? `${rental.duration_minutes} мин` : ''}
          {rental.compensation_minutes > 0 ? ` · −${rental.compensation_minutes} мин Signature` : ''}
          {waiting > 0 ? ` · ожидание ${formatMoney(waiting)}` : ''}
        </div>
      </div>
    </div>
  )
}

export default function ProfilePage() {
  const { user } = useAuth()
  const { hash } = useLocation()

  // Из меню «Телефон и данные» — сразу к форме контактов.
  useEffect(() => {
    if (hash === '#settings') document.getElementById('settings')?.scrollIntoView({ behavior: 'smooth' })
  }, [hash])
  const { data: rentals = [], isLoading } = useRentalHistory()

  const completed = rentals.filter((rental) => rental.status === 'completed')
  const totalSpent = rentals.reduce((sum, rental) => sum + Number(rental.total_cost || 0), 0)
  const totalMinutes = completed.reduce((sum, rental) => sum + (rental.duration_minutes || 0), 0)

  const stats = [
    [IconRoute, completed.length, 'Поездок'],
    [IconClock, totalMinutes, 'Минут в пути'],
    [IconShield, formatMoney(totalSpent), 'Потрачено'],
  ]

  return (
    <div className="profile fade-up">
      <header className="page-head">
        <div className="overline">Личный кабинет</div>
        <h1 className="display drip">Мои поездки</h1>
      </header>

      <RentalStatusWidget />

      <div className="profile-layout">
        <div className="profile-main">
          <div className="stats">
            {stats.map(([Icon, value, label], index) => (
              <div className="stat" key={label} style={{ animationDelay: `${index * 60}ms` }}>
                <span className="stat__icon">
                  <Icon width={18} height={18} />
                </span>
                <div className="stat__value">{value}</div>
                <div className="stat__label">{label}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <h2>История поездок</h2>

            {isLoading &&
              Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="skeleton" style={{ height: 72, marginTop: 12 }} />
              ))}

            {!isLoading && rentals.length === 0 && (
              <div className="empty">
                <p>Поездок пока нет</p>
                <Link to="/" className="btn btn--cta">
                  Выбрать автомобиль
                </Link>
              </div>
            )}

            <div className="trips">
              {rentals.map((rental, index) => (
                <TripItem key={rental.id} rental={rental} index={index} />
              ))}
            </div>
          </div>
        </div>

        <div className="profile-side">
          <RuliIdCard access={user.access} />
          <InstallCard />
          <ProfileForm />
        </div>
      </div>
    </div>
  )
}
