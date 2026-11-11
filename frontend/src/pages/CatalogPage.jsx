import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import CarCard from '../components/CarCard'
import CarMap from '../components/CarMap'
import CarSheet from '../components/CarSheet'
import ErrorBoundary from '../components/ErrorBoundary'
import FilterChips from '../components/FilterChips'
import FilterPanel from '../components/FilterPanel'
import MapPanel from '../components/MapPanel'
import RentalStatusWidget from '../components/RentalStatusWidget'
import { IconChevron, IconPin, IconRefresh, IconSpark, IconUser } from '../components/icons'
import { useCars, useWalkRoute } from '../hooks/useCars'
import { useIsMobile } from '../hooks/useMediaQuery'
import { useCurrentRental } from '../hooks/useRentals'
import { LOCATION_HINTS, useUserLocation } from '../location/LocationContext'
import { PlannerBar, PlannerResults } from '../planner/TripPlanner'
import { reverseGeocode, useTripPlan } from '../planner/usePlanner'
import { Avatar } from '../shell/TopBar'
import { useTheme } from '../theme/ThemeProvider'
import { useUi } from '../ui/UiProvider'
import { isBookable } from '../utils/carVisual'
import { formatWalk } from '../utils/walk'

const EMPTY_FILTERS = {
  search: '',
  car_class: '',
  transmission: '',
  fuel_type: '',
  max_price: '',
  ordering: '',
  onlyAvailable: true,
}

// Один и тот же пустой массив, пока данных нет: новый [] на каждый рендер заставлял бы карту перерисовываться.
const NO_CARS = []

function segmentLength([lng1, lat1], [lng2, lat2]) {
  const kx = 111_320 * Math.cos((lat1 * Math.PI) / 180)
  return Math.hypot((lng2 - lng1) * kx, (lat2 - lat1) * 110_540)
}

/** Точка на ломаной маршрута на доле пути t ∈ [0, 1]. */
function pointAlong(coordinates, lengths, total, t) {
  let left = total * t
  for (let i = 1; i < coordinates.length; i += 1) {
    if (left <= lengths[i - 1] || i === coordinates.length - 1) {
      const k = lengths[i - 1] ? Math.min(1, left / lengths[i - 1]) : 1
      const [a, b] = [coordinates[i - 1], coordinates[i]]
      return { lng: a[0] + (b[0] - a[0]) * k, lat: a[1] + (b[1] - a[1]) * k }
    }
    left -= lengths[i - 1]
  }
  const [lng, lat] = coordinates[coordinates.length - 1]
  return { lng, lat }
}

export default function CatalogPage({ onMenu }) {
  const mobile = useIsMobile()
  const { theme } = useTheme()
  const { user, isAuthenticated } = useAuth()
  const [params, setParams] = useSearchParams()
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [selectedId, setSelectedId] = useState(null)
  const [walker, setWalker] = useState(null)
  const [alternative, setAlternative] = useState(null)
  const [snap, setSnap] = useState('peek')
  const [destination, setDestination] = useState(null)
  const [picking, setPicking] = useState(false)
  const [chosenOption, setChosenOption] = useState(null)
  const walkFrameRef = useRef(0)
  const { location, locate, setManualLocation } = useUserLocation()
  const { data: rental } = useCurrentRental()
  const { notify } = useUi()

  const { onlyAvailable, ...rest } = filters
  const {
    data: cars = NO_CARS,
    isLoading,
    isError,
    isFetching,
    refetch,
  } = useCars({ ...rest, status: onlyAvailable ? 'available' : '' }, location)
  const planQuery = useTripPlan(location, destination)

  // Ярлык «Куда едем?» с главного экрана телефона открывает выбор точки.
  useEffect(() => {
    if (params.get('plan')) {
      setPicking(true)
      setSnap('peek')
      params.delete('plan')
      setParams(params, { replace: true })
    }
  }, [])

  const planCars = planQuery.data?.options?.map((option) => option.car) || NO_CARS
  const selectedCar =
    cars.find((car) => car.id === selectedId) ||
    planCars.find((car) => car.id === selectedId) ||
    (alternative && alternative.id === selectedId ? alternative : null)
  const activeSelectedId = selectedCar ? selectedId : null

  // Забронированная машина остаётся на карте и подсвечена, к ней строится маршрут.
  const reservedCar = rental?.status === 'reserved' ? rental.car : null
  const mapCars = useMemo(() => {
    const extra = [reservedCar, selectedCar].filter(
      (car, index, list) =>
        car && !cars.some((item) => item.id === car.id) && list.findIndex((c) => c?.id === car.id) === index,
    )
    return extra.length ? [...cars, ...extra] : cars
  }, [cars, reservedCar, selectedCar])
  const routeCarId = activeSelectedId ?? reservedCar?.id ?? null
  const { data: walkRoute } = useWalkRoute(routeCarId, location)
  // Когда клиент уже у машины, линия в пару метров и «0 м» только мешают.
  const route = walkRoute && walkRoute.distance_m >= 30 ? walkRoute : null
  const plan = planQuery.data
  const tripRoute =
    destination && plan?.route && (!chosenOption || chosenOption.car.id === plan.best_car_id) ? plan.route : null

  // «Ближайшая» — только та, которую этому водителю можно взять прямо сейчас.
  const nearest = cars
    .filter((car) => car.walk && isBookable(car))
    .reduce((best, car) => (!best || car.walk.duration_s < best.walk.duration_s ? car : best), null)

  useEffect(() => () => cancelAnimationFrame(walkFrameRef.current), [])
  useEffect(() => {
    if (!reservedCar) {
      cancelAnimationFrame(walkFrameRef.current)
      setWalker(null)
    }
  }, [reservedCar?.id])

  // Бронь или поездка — шторка хотя бы наполовину, чтобы были видны таймер и кнопки.
  useEffect(() => {
    if (rental) setSnap((current) => (current === 'peek' ? 'half' : current))
  }, [rental?.id, rental?.status])

  const select = (car) => {
    // Нажатие на свою бронь не открывает карточку — управление в виджете брони.
    if (car && reservedCar && car.id === reservedCar.id) {
      setSelectedId(null)
      setSnap('half')
      return
    }
    setSelectedId(car?.id ?? null)
    if (car) setSnap('half')
  }

  const handleLocate = async () => {
    const result = await locate()
    if (result.reason) notify('Местоположение', { description: LOCATION_HINTS[result.reason], tone: 'info' })
    return result
  }

  const handleSetLocation = (lat, lng) => {
    setManualLocation(lat, lng)
    notify('Точка отправления изменена', {
      description: 'Время пешком пересчитано от отмеченного места.',
      tone: 'info',
    })
  }

  const chooseDestination = (point) => {
    setDestination(point)
    setPicking(false)
    setSelectedId(null)
    setChosenOption(null)
    setSnap('half')
  }

  const handlePick = async (lat, lng) => {
    setPicking(false)
    chooseDestination({ title: 'Точка на карте', subtitle: 'Уточняем адрес…', lat, lng })
    const place = await reverseGeocode(lat, lng)
    setDestination((current) => (current && current.lat === lat && current.lng === lng ? { ...place, lat, lng } : current))
  }

  const clearPlanner = () => {
    setDestination(null)
    setPicking(false)
    setChosenOption(null)
    setSelectedId(null)
  }

  const chooseOption = (option) => {
    setChosenOption(option)
    setSelectedId(option.car.id)
    setSnap('half')
  }

  /** «Машины нет на месте»: замену показываем на карте с открытой карточкой. */
  const handleShowAlternative = (car) => {
    setAlternative({ ...car, shown: true })
    setSelectedId(car.id)
    setSnap('half')
  }

  const closeSheet = () => {
    setSelectedId(null)
    setChosenOption(null)
    if (alternative?.shown) setAlternative(null)
  }

  /** Демо для защиты: метка клиента проходит по маршруту до забронированной машины. */
  const handleDemoWalk = () => {
    if (!reservedCar) return
    const ownRoute = routeCarId === reservedCar.id ? route : null
    const coordinates =
      ownRoute?.geometry?.length > 1
        ? ownRoute.geometry
        : [
            [location.lng, location.lat],
            [reservedCar.longitude, reservedCar.latitude],
          ]
    const lengths = coordinates.slice(1).map((point, i) => segmentLength(coordinates[i], point))
    const total = lengths.reduce((sum, length) => sum + length, 0)
    const duration = Math.min(7000, Math.max(2500, total * 4))
    const startedAt = performance.now()
    setSelectedId(null)
    setSnap('peek')
    cancelAnimationFrame(walkFrameRef.current)

    const tick = (time) => {
      const t = Math.min(1, (time - startedAt) / duration)
      const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2
      setWalker(pointAlong(coordinates, lengths, total, eased))
      if (t < 1) {
        walkFrameRef.current = requestAnimationFrame(tick)
        return
      }
      setWalker(null)
      setSnap('half')
      setManualLocation(reservedCar.latitude - 0.00012, reservedCar.longitude + 0.00008)
      notify('Вы у машины', {
        description: 'Осмотрите кузов и салон — акт осмотра защитит вас от чужих повреждений.',
        tone: 'info',
      })
    }
    walkFrameRef.current = requestAnimationFrame(tick)
  }

  const plannerBar = (
    <PlannerBar
      destination={destination}
      picking={picking}
      onDestination={chooseDestination}
      onTogglePick={() => {
        setPicking((value) => !value)
        setSnap('peek')
      }}
      onClear={clearPlanner}
    />
  )

  let content
  if (picking) {
    content = (
      <div className="pick-hint">
        <IconPin width={22} height={22} />
        <div>
          <b>Нажмите на карту — куда едем</b>
          <p className="muted">Покажем, какая машина рядом выйдет дешевле до этой точки.</p>
        </div>
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => setPicking(false)}>
          Отмена
        </button>
      </div>
    )
  } else if (selectedCar) {
    content = (
      <CarSheet
        car={selectedCar}
        trip={chosenOption?.car.id === selectedCar.id ? chosenOption : null}
        destination={destination}
        onBack={destination ? () => setSelectedId(null) : null}
        onClose={closeSheet}
      />
    )
  } else if (destination) {
    content = <PlannerResults destination={destination} query={planQuery} onChoose={chooseOption} onClear={clearPlanner} />
  } else {
    content = (
      <section className="nearby">
        <div className="nearby__head">
          <div>
            <h3>
              {isLoading ? 'Ищем машины…' : `Рядом ${cars.length} авто`}
            </h3>
            <p className="muted">
              {filters.ordering ? 'Отсортировано по выбранному признаку' : `от точки «${location.label}»`}
              {nearest && !filters.ordering && ` · ближайшая в ${formatWalk(nearest.walk).time}`}
            </p>
          </div>
          <button
            type="button"
            className={`btn btn--soft btn--sm ${filtersOpen ? 'is-open' : ''}`}
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
          >
            Фильтры
            <IconChevron width={14} height={14} />
          </button>
        </div>
        <div className={`collapse ${filtersOpen ? 'is-open' : ''}`}>
          <div className="collapse__inner">
            <FilterPanel filters={filters} onChange={setFilters} />
          </div>
        </div>
        {isError && (
          <div className="notice notice--warn">
            Не удалось загрузить автомобили.
            <button type="button" className="btn btn--soft btn--sm" onClick={() => refetch()}>
              <IconRefresh width={15} height={15} />
              Повторить
            </button>
          </div>
        )}
        {isLoading && (
          <div className="car-list">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="skeleton skeleton--row" />
            ))}
          </div>
        )}
        {!isLoading && !isError && cars.length === 0 && (
          <div className="state">По заданным фильтрам машин нет</div>
        )}
        <div className="car-list">
          {cars.map((car, index) => (
            <CarCard
              key={car.id}
              car={car}
              index={index}
              nearest={!filters.ordering && car.id === nearest?.id}
              onSelect={select}
            />
          ))}
        </div>
        <p className="fine-print map-tip">
          <IconSpark width={13} height={13} /> Правый клик или долгое нажатие по карте — отметить, где вы стоите.
        </p>
      </section>
    )
  }

  const header = (
    <div className="map-panel__header">
      {!mobile && plannerBar}
      <FilterChips filters={filters} onChange={setFilters} />
    </div>
  )

  return (
    <div className={`map-page ${picking ? 'is-picking' : ''}`}>
      <div className="map-stage">
        <ErrorBoundary fallback={<div className="map-fallback">Карта временно недоступна — список машин работает.</div>}>
          <CarMap
            key={theme}
            theme={theme}
            cars={mapCars}
            selectedId={activeSelectedId ?? reservedCar?.id ?? null}
            onSelect={select}
            userLocation={walker ? { ...location, ...walker } : location}
            route={routeCarId ? route : null}
            onLocate={handleLocate}
            onSetLocation={handleSetLocation}
            onRefresh={() => refetch()}
            refreshing={isFetching}
            fitKey={isFetching ? null : JSON.stringify(filters)}
            destination={destination}
            tripRoute={tripRoute}
            picking={picking}
            onPickPoint={handlePick}
          />
        </ErrorBoundary>
      </div>

      {mobile && (
        <div className="map-top">
          {plannerBar}
          {isAuthenticated ? (
            <Avatar user={user} onClick={onMenu} />
          ) : (
            <button type="button" className="icon-btn map-top__menu" onClick={onMenu} aria-label="Меню">
              <IconUser />
            </button>
          )}
        </div>
      )}

      <MapPanel mobile={mobile} snap={snap} onSnap={setSnap} header={header}>
        <RentalStatusWidget
          onDemoWalk={handleDemoWalk}
          walking={Boolean(walker)}
          alternative={alternative?.shown ? null : alternative}
          onAlternative={setAlternative}
          onShowAlternative={handleShowAlternative}
        />
        {content}
      </MapPanel>
    </div>
  )
}
