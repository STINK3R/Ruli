import { useEffect, useRef, useState } from 'react'
import { extractError } from '../api/client'
import { IconClose, IconFlag, IconPin, IconSearch, IconWalk } from '../components/icons'
import { formatMoney, isCutout } from '../utils/carVisual'
import { useAddressSearch } from './usePlanner'

const BADGES = {
  cheapest: ['Выгоднее всего', 'sticker'],
  fastest: ['Быстрее всего', 'sticker sticker--pink'],
  nearest: ['Ближайшая', 'sticker sticker--outline'],
}

const QUICK = [
  { title: 'Минск-Арена', subtitle: 'пр. Победителей, 111', lat: 53.9361, lng: 27.4818 },
  { title: 'Вокзал', subtitle: 'Привокзальная пл.', lat: 53.8907, lng: 27.5507 },
  { title: 'Аэропорт', subtitle: 'Национальный аэропорт', lat: 53.8825, lng: 28.0307 },
]

/** Строка «Куда едем?»: адрес с подсказками или точка на карте. */
export function PlannerBar({ destination, picking, onDestination, onTogglePick, onClear, compact = false }) {
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(false)
  const { data: suggestions = [], isFetching } = useAddressSearch(query)
  const boxRef = useRef(null)

  useEffect(() => {
    if (destination) setQuery('')
  }, [destination])

  useEffect(() => {
    const onDown = (event) => {
      if (!boxRef.current?.contains(event.target)) setFocused(false)
    }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [])

  const choose = (point) => {
    onDestination(point)
    setFocused(false)
    setQuery('')
  }

  const open = focused && !destination
  const list = query.trim().length >= 3 ? suggestions : QUICK

  return (
    <div ref={boxRef} className={`planner-bar ${open ? 'is-open' : ''} ${compact ? 'planner-bar--compact' : ''}`}>
      <div className="planner-bar__field">
        <IconSearch width={20} height={20} />
        {destination ? (
          <button type="button" className="planner-bar__value" onClick={onClear} title="Сменить адрес">
            <small>Едем до</small>
            <b>{destination.title}</b>
          </button>
        ) : (
          <input
            type="search"
            value={query}
            placeholder={picking ? 'Нажмите на карту, куда едем' : 'Куда едем?'}
            aria-label="Куда едем"
            onFocus={() => setFocused(true)}
            onChange={(event) => setQuery(event.target.value)}
          />
        )}
        {destination ? (
          <button type="button" className="planner-bar__btn" onClick={onClear} aria-label="Сбросить маршрут">
            <IconClose width={16} height={16} />
          </button>
        ) : (
          <button
            type="button"
            className={`planner-bar__btn ${picking ? 'is-active' : ''}`}
            onClick={onTogglePick}
            title="Указать точку на карте"
          >
            <IconPin width={17} height={17} />
          </button>
        )}
      </div>

      {open && (
        <div className="planner-bar__drop">
          {query.trim().length < 3 && <div className="planner-bar__hint">Популярное</div>}
          {isFetching && list.length === 0 && <div className="planner-bar__hint">Ищем адрес…</div>}
          {!isFetching && query.trim().length >= 3 && list.length === 0 && (
            <div className="planner-bar__hint">Ничего не нашли в Минске. Укажите точку на карте.</div>
          )}
          {list.map((item) => (
            <button key={`${item.lat},${item.lng}`} type="button" onClick={() => choose(item)}>
              <IconFlag width={16} height={16} />
              <span>
                <b>{item.title}</b>
                {item.subtitle && <small>{item.subtitle}</small>}
              </span>
            </button>
          ))}
          <button
            type="button"
            className="planner-bar__map"
            onClick={() => {
              setFocused(false)
              onTogglePick()
            }}
          >
            <IconPin width={16} height={16} />
            <span>
              <b>Указать на карте</b>
              <small>Нажмите на место назначения</small>
            </span>
          </button>
        </div>
      )}
    </div>
  )
}

function OptionCard({ option, index, onChoose }) {
  const { car } = option
  const best = option.badges.includes('cheapest')
  return (
    <button
      type="button"
      className={`plan-option ${best ? 'plan-option--best' : ''}`}
      style={{ animationDelay: `${index * 60}ms` }}
      onClick={() => onChoose(option)}
    >
      <div className="plan-option__badges">
        {option.badges.map((badge) => (
          <span key={badge} className={BADGES[badge][1]}>
            {BADGES[badge][0]}
          </span>
        ))}
      </div>
      <div className="plan-option__body">
        {car.image && isCutout(car.image) ? (
          <img className="plan-option__car" src={car.image} alt="" loading="lazy" />
        ) : (
          <span className="plan-option__car plan-option__car--empty" />
        )}
        <div className="plan-option__info">
          <b>{car.title}</b>
          <span className="plan-option__route">
            <IconWalk width={14} height={14} />
            {option.walk_minutes} мин
            <i>→</i>
            {option.trip_minutes} мин за рулём
          </span>
          <small>
            {car.car_class_display} · {option.package}
            {Number(option.waiting_cost) > 0 && ` · ожидание ${formatMoney(option.waiting_cost)}`}
          </small>
        </div>
        <div className="plan-option__price">
          <b className="num">≈ {Number(option.total_cost).toFixed(2).replace('.', ',')}</b>
          <small>BYN · на месте через {option.arrive_minutes} мин</small>
        </div>
      </div>
    </button>
  )
}

/** Результат планировщика: какую машину взять до этой точки. */
export function PlannerResults({ destination, query, onChoose, onClear }) {
  const { data: plan, isLoading, isError, error } = query
  const saving = plan ? Number(plan.saving_vs_nearest) : 0

  return (
    <section className="planner">
      <header className="planner__head">
        <div>
          <span className="overline overline--gold">Куда едем?</span>
          <h3>{destination.title}</h3>
          {destination.subtitle && <p className="muted">{destination.subtitle}</p>}
        </div>
        <button type="button" className="sheet__close" onClick={onClear} aria-label="Закрыть планировщик">
          <IconClose width={16} height={16} />
        </button>
      </header>

      {isLoading && (
        <div className="planner__loading">
          <span className="spray-loader" />
          Считаем маршруты и цены…
        </div>
      )}
      {isError && <p className="error-text">{extractError(error, 'Не удалось посчитать поездку')}</p>}
      {plan && plan.options.length === 0 && <div className="state">{plan.reason || 'Свободных машин нет.'}</div>}

      {plan && plan.options.length > 0 && (
        <>
          {saving > 0.05 ? (
            <div className="planner__tip drip drip--pink">
              Не берите ближайшую: выгодная машина сэкономит <b>{formatMoney(saving)}</b> на этой поездке.
            </div>
          ) : (
            <div className="planner__tip">Ближайшая машина — и есть самая выгодная. Повезло!</div>
          )}
          <div className="planner__list">
            {plan.options.map((option, index) => (
              <OptionCard key={option.car.id} option={option} index={index} onChoose={onChoose} />
            ))}
          </div>
          <p className="fine-print">
            Время за рулём — по маршруту OSRM с запасом 25% на пробки и 3 минуты на парковку. Цена — по лучшему
            тарифу: поминутно или пакетом, бесплатное ожидание — по «Честной брони».
          </p>
        </>
      )}
    </section>
  )
}
