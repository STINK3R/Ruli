import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { extractError } from '../api/client'
import LivenessCheck from '../camera/LivenessCheck'
import { useNow } from '../hooks/useNow'
import { useRewards } from '../hooks/useRewards'
import {
  useCancelRental,
  useCarMissing,
  useCurrentRental,
  useFinishRental,
  useStartRental,
} from '../hooks/useRentals'
import { startTripFaceCheck, submitTripFaceCheck } from '../hooks/useVerification'
import { useUserLocation } from '../location/LocationContext'
import { useUi } from '../ui/UiProvider'
import { bestTripPrice, carTopViewSvg, formatMoney, isCutout } from '../utils/carVisual'
import { formatWalk } from '../utils/walk'
import InspectionModal from './InspectionModal'
import { IconCamera, IconCheck, IconFace, IconWalk } from './icons'

const CAR_MISSING_RADIUS_M = 300

function formatClock(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(seconds / 3600)
  const minutes = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0')
  const secs = String(seconds % 60).padStart(2, '0')
  return hours ? `${hours}:${minutes}:${secs}` : `${minutes}:${secs}`
}

function distanceM(a, b) {
  const rad = Math.PI / 180
  const dLat = (b.lat - a.lat) * rad
  const dLng = (b.lng - a.lng) * rad
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h))
}

/** Кольцо обратного отсчёта бесплатного ожидания. */
function Ring({ progress, children }) {
  const radius = 34
  const circumference = 2 * Math.PI * radius
  return (
    <div className="ring">
      <svg width="84" height="84" viewBox="0 0 84 84">
        <circle cx="42" cy="42" r={radius} className="ring__track" />
        <circle
          cx="42"
          cy="42"
          r={radius}
          className="ring__value"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - Math.max(0, Math.min(1, progress)))}
        />
      </svg>
      <div className="ring__label">{children}</div>
    </div>
  )
}

function Steps({ rental }) {
  const kinds = new Set(rental.inspections.map((item) => item.kind))
  const face = rental.face_check || {}
  const started = rental.status === 'active' || kinds.has('finish')
  const steps = [
    ['Осмотр', kinds.has('start')],
    ...(face.required ? [['Лицо', face.passed || started]] : []),
    ['Поездка', started],
    ['Осмотр', kinds.has('finish')],
  ]
  return (
    <ol className="steps-line">
      {steps.map(([label, done], index) => (
        <li key={index} className={done ? 'is-done' : ''}>
          <span>{done ? <IconCheck width={11} height={11} strokeWidth={3} /> : index + 1}</span>
          {label}
        </li>
      ))}
    </ol>
  )
}

function AlternativePanel({ alternative, floating, onClose, onShow }) {
  const walk = alternative.walk ? formatWalk(alternative.walk) : null
  return (
    <section className={`rental-widget ${floating ? 'rental-widget--floating' : ''}`}>
      <div className="rental-widget__car">
        {isCutout(alternative.image) && (
          <img className="rental-widget__photo" src={alternative.image} alt="" />
        )}
        <div>
          <div className="rental-widget__status">Бронь снята без оплаты · замена рядом</div>
          <h3>{alternative.title}</h3>
          <div className="rental-widget__meta">
            {walk ? `${walk.time} пешком · ` : ''}
            {alternative.address}
            {alternative.free_booking_minutes ? ` · бронь бесплатна ${alternative.free_booking_minutes} мин` : ''}
          </div>
        </div>
      </div>
      <div className="rental-widget__actions">
        {onShow ? (
          <button className="btn btn--cta" onClick={() => onShow(alternative)}>
            Показать на карте
          </button>
        ) : (
          <Link className="btn btn--cta" to={`/cars/${alternative.id}`}>
            Открыть машину
          </Link>
        )}
        <button className="btn btn--ghost-light" onClick={onClose}>
          Понятно
        </button>
      </div>
    </section>
  )
}

export default function RentalStatusWidget({
  floating = false,
  onDemoWalk,
  walking = false,
  alternative: liftedAlternative,
  onAlternative,
  onShowAlternative,
}) {
  const { data: rental } = useCurrentRental()
  const start = useStartRental()
  const finish = useFinishRental()
  const cancel = useCancelRental()
  const carMissing = useCarMissing()
  const { location } = useUserLocation()
  const { notify, showTripSummary } = useUi()
  const [inspecting, setInspecting] = useState(null)
  const [faceOpen, setFaceOpen] = useState(false)
  const [usePoints, setUsePoints] = useState(false)
  const { data: rewards } = useRewards()
  const queryClient = useQueryClient()
  // Каталог держит замену у себя (переживает смену «Карта/Список»), профиль — локально.
  const [localAlternative, setLocalAlternative] = useState(null)
  const alternative = onAlternative ? liftedAlternative : localAlternative
  const setAlternative = onAlternative || setLocalAlternative
  const now = useNow(Boolean(rental))

  // Ошибка прошлого действия не должна висеть под виджетом после смены статуса брони.
  const rentalState = rental ? `${rental.id}:${rental.status}` : ''
  useEffect(() => {
    ;[start, finish, cancel].forEach((mutation) => mutation.reset())
  }, [rentalState])

  if (!rental) {
    return alternative ? (
      <AlternativePanel
        alternative={alternative}
        floating={floating}
        onClose={() => setAlternative(null)}
        onShow={onShowAlternative}
      />
    ) : null
  }

  const { car } = rental
  const isActive = rental.status === 'active'
  const inspected = new Set(rental.inspections.map((item) => item.kind))
  const pending = start.isPending || finish.isPending || cancel.isPending || carMissing.isPending
  const error = start.error || finish.error || cancel.error || carMissing.error

  const reservedAt = new Date(rental.reserved_at).getTime()
  const freeUntil = new Date(rental.free_waiting_until).getTime()
  const freeTotal = (freeUntil - reservedAt) / 1000
  const freeLeft = (freeUntil - now) / 1000
  const paidWaitingMinutes = freeLeft < 0 ? Math.ceil(-freeLeft / 60) : 0
  const accruedWaiting = paidWaitingMinutes * Number(rental.waiting_price_per_minute_at_booking)

  const elapsed = isActive ? (now - new Date(rental.started_at).getTime()) / 1000 : 0
  const billable = Math.max(0, Math.ceil(elapsed / 60) - rental.compensation_minutes)
  const tripEstimate =
    (billable > 0
      ? bestTripPrice(
          Math.max(1, billable),
          Number(rental.price_per_minute_at_booking),
          Number(rental.price_per_hour_at_booking),
          Number(rental.price_per_day_at_booking),
        )
      : 0) + Number(rental.waiting_cost || 0)

  const nearCar =
    location && distanceM(location, { lat: car.latitude, lng: car.longitude }) <= CAR_MISSING_RADIUS_M

  const needsFace = rental.face_check?.required && !rental.face_check?.passed
  const handleStart = () =>
    start.mutate(rental.id, {
      onSuccess: () => notify('Поездка началась', { description: 'Машина открыта. Хорошей дороги!' }),
    })
  const handleFacePassed = (updated) => {
    queryClient.setQueryData(['rental', 'current'], updated)
    setFaceOpen(false)
    handleStart()
  }
  const handleFinish = () =>
    finish.mutate({ rentalId: rental.id, usePoints }, { onSuccess: ({ data }) => showTripSummary(data) })
  // До 30% поездки баллами, 1 балл = 0,01 BYN — та же формула, что на сервере.
  const pointsCanSpend = rewards ? Math.min(rewards.balance, Math.floor(tripEstimate * 30)) : 0
  const handleCancel = () =>
    cancel.mutate(rental.id, {
      onSuccess: ({ data }) =>
        notify('Бронь отменена', {
          description:
            Number(data.total_cost) > 0
              ? `Списано за ожидание: ${formatMoney(data.total_cost)}`
              : 'В пределах бесплатного ожидания — без списаний',
        }),
    })
  const handleMissing = () =>
    carMissing.mutate(
      { rentalId: rental.id, location },
      {
        onSuccess: ({ data }) => {
          setAlternative(data.alternative)
          notify('Бронь снята без оплаты', {
            description: 'Спасибо! Машину проверит оператор по GPS.',
          })
        },
      },
    )

  return (
    <section className={`rental-widget ${floating ? 'rental-widget--floating' : ''}`}>
      <div className="rental-widget__car">
        {isCutout(car.image) ? (
          <img className="rental-widget__photo" src={car.image} alt="" />
        ) : (
          <span
            className="rental-widget__silhouette"
            dangerouslySetInnerHTML={{ __html: carTopViewSvg(car, { width: 30 }) }}
          />
        )}
        <div>
          <div className="rental-widget__status">
            <span className="rental-widget__live" />
            {isActive ? 'В поездке' : 'Забронирован'}
          </div>
          <h3>{car.title}</h3>
          <div className="rental-widget__meta">
            {car.license_plate}
            {car.address ? ` · ${car.address}` : ''}
          </div>
          <Steps rental={rental} />
        </div>
      </div>

      <div className="rental-widget__stats">
        {isActive ? (
          <>
            <div>
              <div className="rental-widget__stat-value">{formatClock(elapsed)}</div>
              <div className="rental-widget__stat-label">В пути</div>
            </div>
            <div>
              <div className="rental-widget__stat-value">{formatMoney(tripEstimate)}</div>
              <div className="rental-widget__stat-label">
                {rental.compensation_minutes
                  ? `Signature: ${rental.compensation_minutes} мин бесплатно`
                  : 'Сейчас к оплате'}
              </div>
            </div>
          </>
        ) : freeLeft > 0 ? (
          <Ring progress={freeLeft / freeTotal}>
            <b>{formatClock(freeLeft)}</b>
            <span>бесплатно</span>
          </Ring>
        ) : (
          <div>
            <div className="rental-widget__stat-value">{formatMoney(accruedWaiting)}</div>
            <div className="rental-widget__stat-label">
              Платное ожидание · {formatMoney(rental.waiting_price_per_minute_at_booking)}/мин
            </div>
          </div>
        )}
      </div>

      <div className="rental-widget__actions">
        {isActive ? (
          inspected.has('finish') ? (
            <>
              {pointsCanSpend > 0 && (
                <label className="points-toggle">
                  <input type="checkbox" checked={usePoints} onChange={(event) => setUsePoints(event.target.checked)} />
                  <span>
                    <b>Оплатить баллами</b>
                    <small>
                      −{formatMoney(pointsCanSpend / 100)} · спишется {pointsCanSpend} из {rewards.balance}
                    </small>
                  </span>
                </label>
              )}
              <button className="btn btn--cta" disabled={pending} onClick={handleFinish}>
                Завершить поездку
              </button>
            </>
          ) : (
            <button className="btn btn--cta" onClick={() => setInspecting('finish')}>
              <IconCamera width={18} height={18} />
              Осмотр перед завершением
            </button>
          )
        ) : (
          <>
            {inspected.has('start') && needsFace ? (
              <button className="btn btn--cta" disabled={pending} onClick={() => setFaceOpen(true)}>
                <IconFace width={18} height={18} />
                За рулём я — открыть машину
              </button>
            ) : inspected.has('start') ? (
              <button className="btn btn--cta" disabled={pending} onClick={handleStart}>
                Начать поездку
              </button>
            ) : (
              <button className="btn btn--cta" onClick={() => setInspecting('start')}>
                <IconCamera width={18} height={18} />
                Осмотреть машину
              </button>
            )}
            <div className="rental-widget__secondary">
              {nearCar ? (
                <button className="btn btn--ghost-light" disabled={pending} onClick={handleMissing}>
                  Машины нет на месте
                </button>
              ) : (
                onDemoWalk && (
                  <button className="btn btn--ghost-light" disabled={walking} onClick={onDemoWalk}>
                    <IconWalk width={16} height={16} />
                    {walking ? 'Идём…' : 'Демо: дойти до машины'}
                  </button>
                )
              )}
              <button className="btn btn--outline-light" disabled={pending} onClick={handleCancel}>
                Отменить
              </button>
            </div>
          </>
        )}
      </div>

      {error && <p className="error-text rental-widget__error">{extractError(error)}</p>}

      {inspecting && (
        <InspectionModal rental={rental} kind={inspecting} onClose={() => setInspecting(null)} />
      )}
      {faceOpen && (
        <LivenessCheck
          title="Кто за рулём?"
          intro={
            <p className="liveness__intro">
              Машина откроется только владельцу аккаунта: 5 секунд перед фронтальной камерой. Так ваш аккаунт не
              передадут другу без прав.
            </p>
          }
          demoMode={rental.face_check?.demo}
          start={() => startTripFaceCheck(rental.id)}
          submit={(check, frames, demo) => submitTripFaceCheck(rental.id, check, frames, demo)}
          onPassed={handleFacePassed}
          onClose={() => setFaceOpen(false)}
        />
      )}
    </section>
  )
}
