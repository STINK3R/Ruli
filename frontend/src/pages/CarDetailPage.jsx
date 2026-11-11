import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import CarMap from '../components/CarMap'
import { BookingButton, Plate } from '../components/CarSheet'
import ErrorBoundary from '../components/ErrorBoundary'
import PassportModal from '../components/PassportModal'
import {
  IconArrowLeft,
  IconCamera,
  IconCheck,
  IconChevron,
  IconEngine,
  IconFuel,
  IconGearbox,
  IconPin,
  IconSeal,
  IconSeat,
  IconWalk,
} from '../components/icons'
import { useCar, useWalkRoute } from '../hooks/useCars'
import { usePassport } from '../hooks/usePassport'
import { useUserLocation } from '../location/LocationContext'
import { carTopViewSvg, engineLabel, formatMoney, isCutout, isSignature } from '../utils/carVisual'
import { plural } from '../utils/plural'
import { formatWalk } from '../utils/walk'

const STEPS = [
  ['Бронь по маршруту', 'Бесплатное ожидание считается по реальному пешему пути до машины — от 10 до 30 минут.'],
  ['Осмотр с фото', 'Четыре ракурса и отметки на силуэте. Акт запечатывается в паспорт кузова.'],
  ['Поездка', 'Поминутно, а пакеты «Час» и «Сутки» применяются сами, если так дешевле.'],
  ['Завершение', 'Короткий осмотр — и чек. Чужие повреждения вам не припишут.'],
]

export default function CarDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { location } = useUserLocation()
  const { data: car, isLoading, isError } = useCar(id)
  const { data: walkRoute } = useWalkRoute(car?.id, location)
  const { data: passport } = usePassport(car?.id, Boolean(car))
  const [passportOpen, setPassportOpen] = useState(false)

  if (isLoading) {
    return (
      <div className="detail-grid">
        <div className="skeleton" style={{ height: 380 }} />
        <div className="skeleton" style={{ height: 520 }} />
      </div>
    )
  }
  if (isError || !car) return <div className="state">Автомобиль не найден</div>

  const signature = isSignature(car)
  const walk = walkRoute ? formatWalk(walkRoute) : null
  const specs = [
    [IconGearbox, 'Коробка', car.transmission_display],
    [IconEngine, 'Двигатель', engineLabel(car)],
    [IconFuel, 'Топливо', `${car.fuel_type_display} · ${car.fuel_level_percent}%`],
    [IconSeat, 'Мест', car.seats],
  ]

  return (
    <div className="detail fade-up">
      <Link to="/" className="back-link">
        <IconArrowLeft width={16} height={16} />
        Назад к карте
      </Link>

      <div className="detail-grid">
        <div className="detail-main">
          <div
            className={`detail-photo ${isCutout(car.image) ? 'studio' : ''} ${signature ? 'is-signature' : ''}`}
          >
            {signature && (
              <span className="seal-badge seal-badge--lg" title={car.livery_display}>
                Р
              </span>
            )}
            <div className="detail-photo__caption">
              <div className={`overline ${car.car_class === 'premium' ? 'overline--premium' : ''}`}>
                {car.car_class === 'premium' && '◆ '}
                {car.car_class_display} · {car.year}
              </div>
              <h1 className="display">{car.title}</h1>
            </div>
            {car.image ? (
              <img src={car.image} alt={car.title} />
            ) : (
              <span dangerouslySetInnerHTML={{ __html: carTopViewSvg(car, { width: 130 }) }} />
            )}
          </div>

          <div className="card">
            <h2>Характеристики</h2>
            <div className="spec-grid">
              {specs.map(([Icon, label, value]) => (
                <div key={label} className="spec">
                  <Icon width={18} height={18} />
                  <div>
                    <div className="spec__label">{label}</div>
                    <div className="spec__value">{value}</div>
                  </div>
                </div>
              ))}
            </div>
            {car.features.length > 0 && (
              <ul className="features">
                {car.features.map((feature) => (
                  <li key={feature}>
                    <IconCheck width={14} height={14} strokeWidth={2.6} />
                    {feature}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <h2>Как устроена поездка в «Рули»</h2>
            <ol className="steps">
              {STEPS.map(([title, text], index) => (
                <li key={title}>
                  <span className="steps__num">{index + 1}</span>
                  <div>
                    <div className="steps__title">{title}</div>
                    <div className="muted">{text}</div>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>

        <aside className="detail-side">
          <div className="card card--sticky">
            <div className="sheet__chips">
              <Plate number={car.license_plate} />
              {signature ? (
                <span className="tag tag--signature">
                  <IconSeal width={13} height={13} />
                  {car.livery_display}
                </span>
              ) : (
                <span className="tag">Без оклейки</span>
              )}
              {car.status !== 'available' && (
                <span className={`badge badge--${car.status}`}>{car.status_display}</span>
              )}
            </div>

            {car.address && (
              <div className="address-line">
                <IconPin width={16} height={16} />
                {car.address}
              </div>
            )}
            {walk && (
              <div className="sheet__walk">
                <IconWalk width={17} height={17} />
                <span>
                  <b>
                    {walkRoute.source === 'estimate' && '≈ '}
                    {walk.time}
                  </b>{' '}
                  пешком · {walk.distance}
                </span>
              </div>
            )}

            <div className="tariff-box">
              <div className="tariff-box__head">
                <div>
                  <div className="tariff-box__name">Тариф «{car.tariff.name}»</div>
                  <div className="tariff-box__price">
                    {Number(car.tariff.price_per_minute).toFixed(2).replace('.', ',')}
                    <span>BYN/мин</span>
                  </div>
                </div>
              </div>
              <div className="tariff-box__list">
                <div>
                  <span>Ожидание</span>
                  <b>{formatMoney(car.tariff.waiting_price_per_minute)}/мин</b>
                </div>
                {car.tariff.price_per_hour && (
                  <div>
                    <span>Пакет «Час»</span>
                    <b>{formatMoney(car.tariff.price_per_hour)}</b>
                  </div>
                )}
                {car.tariff.price_per_day && (
                  <div>
                    <span>Пакет «Сутки»</span>
                    <b>{formatMoney(car.tariff.price_per_day)}</b>
                  </div>
                )}
                <p>Пакет применится сам, если поездка по нему выйдет дешевле.</p>
              </div>
            </div>

            <button type="button" className="passport-row" onClick={() => setPassportOpen(true)}>
              <span>
                <IconCamera width={16} height={16} />
                <b>Паспорт кузова</b>
                {passport
                  ? ` · ${plural(passport.damages.length, ['отметка', 'отметки', 'отметок'])}`
                  : ''}
              </span>
              <IconChevron width={16} height={16} />
            </button>

            <BookingButton car={car} onBooked={() => navigate('/')} />
          </div>

          <div className="detail-map">
            <ErrorBoundary fallback={<div className="map-fallback">Карта недоступна</div>}>
              <CarMap cars={[car]} interactive={false} />
            </ErrorBoundary>
          </div>
        </aside>
      </div>

      {passportOpen && <PassportModal car={car} onClose={() => setPassportOpen(false)} />}
    </div>
  )
}
