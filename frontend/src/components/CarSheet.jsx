import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { extractError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { usePassport } from '../hooks/usePassport'
import { useBookCar, useCurrentRental } from '../hooks/useRentals'
import { useUserLocation } from '../location/LocationContext'
import { useUi } from '../ui/UiProvider'
import {
  carTopViewSvg,
  engineLabel,
  formatMoney,
  freeWaitingMinutes,
  isCutout,
  isSignature,
} from '../utils/carVisual'
import { plural } from '../utils/plural'
import { formatWalk } from '../utils/walk'
import PassportModal from './PassportModal'
import {
  IconArrowLeft,
  IconCheck,
  IconChevron,
  IconClose,
  IconEngine,
  IconFuel,
  IconGearbox,
  IconInfo,
  IconLock,
  IconPin,
  IconRoute,
  IconSeal,
  IconSeat,
  IconWalk,
} from './icons'

const MARKS = ['отметка', 'отметки', 'отметок']

function CarVisual({ car }) {
  if (isCutout(car.image)) {
    return (
      <img key={car.id} className="sheet-car sheet-car--cutout" src={car.image} alt={car.title} />
    )
  }
  if (car.image) {
    return (
      <div key={car.id} className="sheet-car sheet-car--framed">
        <img src={car.image} alt={car.title} />
      </div>
    )
  }
  return (
    <span
      key={car.id}
      className="sheet-car sheet-car--svg"
      dangerouslySetInnerHTML={{ __html: carTopViewSvg(car, { width: 62 }) }}
    />
  )
}

export function Plate({ number }) {
  return (
    <span className="plate">
      <i>BY</i>
      {number}
    </span>
  )
}

export function BookingButton({ car, onBooked }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { isAuthenticated } = useAuth()
  const { data: currentRental } = useCurrentRental()
  const { location } = useUserLocation()
  const { notify } = useUi()
  const book = useBookCar()

  const eligibility = car.eligibility || {}
  const price = `${formatMoney(car.tariff.price_per_minute)}/мин`

  if (!isAuthenticated) {
    return (
      <button className="btn btn--cta btn--block" onClick={() => navigate('/login', { state: { from: pathname } })}>
        Войти и забронировать
        <span className="btn__price">{price}</span>
      </button>
    )
  }
  if (car.status !== 'available') {
    return (
      <button className="btn btn--cta btn--block" disabled>
        Автомобиль занят
      </button>
    )
  }
  if (!eligibility.allowed) {
    const toKyc = eligibility.code === 'verification' || eligibility.code === 'phone'
    return (
      <div className="locked-cta">
        <div className="locked-cta__text">
          <IconLock width={18} height={18} />
          <span>{eligibility.hint}</span>
        </div>
        <Link className="btn btn--cta btn--block" to={toKyc ? '/verification' : '/profile'}>
          {eligibility.code === 'phone' ? 'Подтвердить телефон' : toKyc ? 'Пройти Рули ID' : 'Как открыть класс'}
        </Link>
      </div>
    )
  }
  if (currentRental) {
    return (
      <button className="btn btn--cta btn--block" disabled>
        У вас уже есть бронь
      </button>
    )
  }

  const handleBook = () =>
    book.mutate(
      { carId: car.id, location },
      {
        onSuccess: ({ data }) => {
          onBooked?.()
          notify(`${car.title} забронирован`, {
            description: `Бесплатное ожидание — ${freeWaitingMinutes(data)} мин. Сначала осмотрите машину.`,
          })
        },
      },
    )

  return (
    <>
      <button className="btn btn--cta btn--block" disabled={book.isPending} onClick={handleBook}>
        {book.isPending ? 'Бронируем…' : 'Забронировать'}
        <span className="btn__price">{price}</span>
      </button>
      {book.error && <p className="error-text">{extractError(book.error)}</p>}
    </>
  )
}

/** Оценка поездки из планировщика «Куда едем?». */
function TripEstimate({ trip, destination }) {
  return (
    <div className="trip-estimate">
      <IconRoute width={18} height={18} />
      <div>
        <small>До «{destination?.title}»</small>
        <b>
          ≈ {trip.trip_minutes} мин за рулём · <span className="num">{formatMoney(trip.total_cost)}</span>
        </b>
        <small>
          {trip.package}
          {trip.badges.includes('cheapest') && ' · самая выгодная машина рядом'}
        </small>
      </div>
    </div>
  )
}

export default function CarSheet({ car, onClose, trip = null, destination = null, onBack = null }) {
  const [aboutOpen, setAboutOpen] = useState(false)
  const [tariffsOpen, setTariffsOpen] = useState(false)
  const [passportOpen, setPassportOpen] = useState(false)
  const { data: passport } = usePassport(car.id, aboutOpen)

  const { tariff } = car
  const signature = isSignature(car)
  const lowFuel = car.fuel_level_percent < 25
  const walk = car.walk ? formatWalk(car.walk) : null

  return (
    <div className="sheet-wrap">
      <CarVisual car={car} />

      <section
        className={`sheet ${isCutout(car.image) || !car.image ? '' : 'sheet--framed'} ${
          signature ? 'sheet--signature' : ''
        }`}
      >
        <div className="sheet__nav">
          {onBack ? (
            <button type="button" className="btn btn--ghost btn--sm" onClick={onBack}>
              <IconArrowLeft width={15} height={15} />К вариантам
            </button>
          ) : (
            <span />
          )}
          <button type="button" className="sheet__close" onClick={onClose} aria-label="Закрыть">
            <IconClose width={16} height={16} />
          </button>
        </div>

        <div className="sheet__head">
          <div className={`overline ${car.car_class === 'premium' ? 'overline--premium' : ''}`}>
            {car.car_class === 'premium' && '◆ '}
            {car.car_class_display} · {car.year}
          </div>
          <h3 className="sheet__title">{car.title}</h3>
          <div className="sheet__chips">
            <Plate number={car.license_plate} />
            <span className={`tag ${lowFuel ? 'tag--low' : ''}`}>
              <IconFuel width={14} height={14} />
              {car.fuel_level_percent}%
            </span>
            {signature ? (
              <span className="tag tag--signature">
                <IconSeal width={13} height={13} />
                Signature
              </span>
            ) : (
              <span className="tag">Без оклейки</span>
            )}
          </div>
        </div>

        {trip && <TripEstimate trip={trip} destination={destination} />}

        {walk && (
          <div className="sheet__walk">
            <IconWalk width={17} height={17} />
            <span>
              <b>
                {car.walk.source === 'estimate' && '≈ '}
                {walk.time}
              </b>{' '}
              пешком · {walk.distance}
            </span>
            {car.free_booking_minutes && (
              <span className="sheet__free">бронь бесплатна {car.free_booking_minutes} мин</span>
            )}
          </div>
        )}

        <div className="sheet__links">
          <a
            className="sheet__address"
            href={`https://yandex.ru/maps/?rtext=~${car.latitude},${car.longitude}&rtt=pd`}
            target="_blank"
            rel="noreferrer"
          >
            <IconPin width={16} height={16} />
            <span>{car.address || 'Маршрут до машины'}</span>
          </a>
          <button
            type="button"
            className={`sheet__about ${aboutOpen ? 'is-open' : ''}`}
            aria-expanded={aboutOpen}
            onClick={() => setAboutOpen((open) => !open)}
          >
            <IconInfo width={16} height={16} />
            Об авто
            <IconChevron width={15} height={15} />
          </button>
        </div>

        <div className={`collapse ${aboutOpen ? 'is-open' : ''}`}>
          <div className="collapse__inner">
            <div className="sheet__specs">
              <span className="tag">
                <IconGearbox width={14} height={14} />
                {car.transmission_display}
              </span>
              <span className="tag">
                <IconEngine width={14} height={14} />
                {engineLabel(car)}
              </span>
              <span className="tag">
                <IconSeat width={14} height={14} />
                {car.seats} мест
              </span>
            </div>
            {car.features.length > 0 && (
              <ul className="sheet__features">
                {car.features.slice(0, 8).map((feature) => (
                  <li key={feature}>
                    <IconCheck width={13} height={13} strokeWidth={2.6} />
                    {feature}
                  </li>
                ))}
              </ul>
            )}
            <button type="button" className="passport-row" onClick={() => setPassportOpen(true)}>
              <span>
                <b>Паспорт кузова</b>
                {passport
                  ? ` · ${plural(passport.damages.length, MARKS)} · ${
                      passport.integrity.ok ? 'цепочка цела' : 'цепочка нарушена'
                    }`
                  : ' · отметки и акты осмотра'}
              </span>
              <IconChevron width={16} height={16} />
            </button>
            <Link to={`/cars/${car.id}`} className="link-gold">
              Полная карточка автомобиля
            </Link>
          </div>
        </div>

        <div className="tariff-box">
          <div className="tariff-box__head">
            <div>
              <div className="tariff-box__name">Тариф «{tariff.name}»</div>
              <div className="tariff-box__price">
                {Number(tariff.price_per_minute).toFixed(2).replace('.', ',')}
                <span>BYN/мин</span>
              </div>
              <div className="tariff-box__sub">
                Ожидание {formatMoney(tariff.waiting_price_per_minute)}/мин
              </div>
            </div>
            <span className="seal-mark" title="Пакеты «Час» и «Сутки» применяются автоматически">
              %
            </span>
          </div>

          <button
            type="button"
            className={`tariff-box__toggle ${tariffsOpen ? 'is-open' : ''}`}
            aria-expanded={tariffsOpen}
            onClick={() => setTariffsOpen((open) => !open)}
          >
            Все тарифы
            <IconChevron width={17} height={17} />
          </button>
          <div className={`collapse ${tariffsOpen ? 'is-open' : ''}`}>
            <div className="collapse__inner">
              <div className="tariff-box__list">
                <div>
                  <span>Поминутно</span>
                  <b>{formatMoney(tariff.price_per_minute)}/мин</b>
                </div>
                {tariff.price_per_hour && (
                  <div>
                    <span>Пакет «Час»</span>
                    <b>{formatMoney(tariff.price_per_hour)}</b>
                  </div>
                )}
                {tariff.price_per_day && (
                  <div>
                    <span>Пакет «Сутки»</span>
                    <b>{formatMoney(tariff.price_per_day)}</b>
                  </div>
                )}
                <p>Пакет применится сам, если поездка по нему выйдет дешевле.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="sheet__footer">
          <BookingButton car={car} onBooked={onClose} />
        </div>
      </section>

      {passportOpen && <PassportModal car={car} onClose={() => setPassportOpen(false)} />}
    </div>
  )
}
