import { carTopViewSvg, isCutout, isLocked, isSignature } from '../utils/carVisual'
import { formatWalk, walkParts } from '../utils/walk'
import { IconLock } from './icons'

/** Строка «Рядом»: слева крупно время пешком — список идёт от ближайшей машины. */
export default function CarCard({ car, index = 0, nearest = false, onSelect }) {
  const walk = car.walk ? formatWalk(car.walk) : null
  const { value: minutes, unit } = walkParts(car.walk)
  const eligibility = car.eligibility || {}
  const locked = isLocked(car)
  const signature = isSignature(car)
  const busy = car.status !== 'available'

  return (
    <button
      type="button"
      className={`car-row ${locked ? 'car-row--locked' : ''} ${busy ? 'car-row--busy' : ''} ${nearest ? 'car-row--nearest' : ''}`}
      style={{ animationDelay: `${Math.min(index, 10) * 40}ms` }}
      onClick={() => onSelect?.(car)}
    >
      <span className="car-row__eta">
        {walk ? (
          <>
            <b className="num">
              {car.walk.source === 'estimate' && <small>≈</small>}
              {minutes}
            </b>
            <span>{unit}</span>
          </>
        ) : (
          <span className="muted">—</span>
        )}
      </span>

      <span className={`car-row__photo ${signature ? 'is-signature' : ''}`}>
        {car.image && isCutout(car.image) ? (
          <img src={car.image} alt="" loading="lazy" />
        ) : (
          <span dangerouslySetInnerHTML={{ __html: carTopViewSvg(car, { width: 26 }) }} />
        )}
      </span>

      <span className="car-row__main">
        <span className="car-row__title">
          {car.title}
          {nearest && <span className="sticker">Рядом</span>}
        </span>
        <span className="car-row__meta">
          {car.car_class_display} · {car.transmission_display}
          {walk && ` · ${walk.distance}`}
        </span>
        {locked ? (
          <span className="car-row__lock">
            <IconLock width={12} height={12} />
            {eligibility.hint}
          </span>
        ) : busy ? (
          <span className="car-row__lock">{car.status_display}</span>
        ) : car.free_booking_minutes > 0 ? (
          <span className="car-row__free">ждём бесплатно {car.free_booking_minutes} мин</span>
        ) : null}
      </span>

      <span className="car-row__price">
        <b className="num">{Number(car.tariff.price_per_minute).toFixed(2).replace('.', ',')}</b>
        <small>BYN/мин</small>
        {signature && <span className="car-row__tag">Signature</span>}
      </span>
    </button>
  )
}
