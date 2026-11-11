import maplibregl from 'maplibre-gl'
import { useEffect, useMemo, useRef, useState } from 'react'
import { carImageId, ensureCarImages } from '../map/carImages'
import { loadMapStyle } from '../map/mapStyle'
import { addPillImage } from '../map/pills'
import { pinPalette } from '../theme'
import { carAngle, isLocked, isSignature } from '../utils/carVisual'
import { formatWalk } from '../utils/walk'
import { IconLocate, IconMinus, IconPlus, IconRefresh } from './icons'

const MINSK = [27.5619, 53.9023]
const EMPTY = { type: 'FeatureCollection', features: [] }
const CLICKABLE = ['car-hit', 'car-icons', 'car-dots', 'selected-icon']

// Переход «точка → силуэт машины» при приближении камеры.
const DOTS_UNTIL = 12.6
const CARS_FROM = 13.3
const CLUSTER_UNTIL = 10
const ICON_SIZE = ['interpolate', ['linear'], ['zoom'], DOTS_UNTIL, 0.42, 15, 0.82, 17.5, 1.25]
const ROUTING_CREDIT =
  '<a href="https://routing.openstreetmap.de" target="_blank" rel="noreferrer">Маршруты © FOSSGIS OSRM</a>'

const WALK_SVG =
  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
  '<circle cx="13" cy="4" r="2"/><path d="m9 21 2.5-6.5L14 17v4M7 12l2.5-4.5 4 1.5 2 3 2.5 1"/></svg>'

/** Координаты в допустимых пределах — иначе MapLibre бросает исключение и карта падает целиком. */
function hasValidPosition(car) {
  return (
    Number.isFinite(car.latitude) &&
    Number.isFinite(car.longitude) &&
    Math.abs(car.latitude) <= 90 &&
    Math.abs(car.longitude) <= 180
  )
}

function toFeature(car, selectedId) {
  return {
    type: 'Feature',
    id: car.id,
    geometry: { type: 'Point', coordinates: [car.longitude, car.latitude] },
    properties: {
      id: car.id,
      icon: carImageId(car),
      angle: carAngle(car.id),
      busy: car.status !== 'available',
      // Гостю показываем всё как обычно; приглушаем только то, что закрыто именно ему.
      locked: isLocked(car),
      signature: isSignature(car),
      premium: car.car_class === 'premium',
      price: Number(car.tariff.price_per_minute).toFixed(2).replace('.', ','),
      selected: car.id === selectedId,
    },
  }
}

function collection(cars) {
  return { type: 'FeatureCollection', features: cars }
}

function addLayers(map, pins) {
  addPillImage(map, 'pill-dark', pins.priceBg, pins.priceStroke)
  addPillImage(map, 'pill-gold', pins.priceSelectedBg, '#0d0e12')

  // Маршрут поездки на машине («Куда едем?») — под пешим маршрутом.
  map.addSource('trip', { type: 'geojson', data: EMPTY })
  map.addLayer({
    id: 'trip-casing',
    type: 'line',
    source: 'trip',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': pins.routeCasing, 'line-width': 10, 'line-opacity': 0.85 },
  })
  map.addLayer({
    id: 'trip-line',
    type: 'line',
    source: 'trip',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': pins.tripLine, 'line-width': 5 },
  })

  map.addSource('route', { type: 'geojson', data: EMPTY })
  map.addSource('cars', {
    type: 'geojson',
    data: EMPTY,
    cluster: true,
    clusterMaxZoom: CLUSTER_UNTIL,
    clusterRadius: 48,
  })
  map.addSource('selected', { type: 'geojson', data: EMPTY })

  map.addLayer({
    id: 'route-casing',
    type: 'line',
    source: 'route',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': pins.routeCasing, 'line-width': 9, 'line-opacity': 0.9 },
  })
  map.addLayer({
    id: 'route-line',
    type: 'line',
    source: 'route',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    // Пунктир баллончиком: круглые точки вдоль пешего маршрута.
    paint: { 'line-color': pins.routeLine, 'line-width': 5, 'line-dasharray': [0, 1.7] },
  })

  const unclustered = ['!', ['has', 'point_count']]
  map.addLayer({
    id: 'clusters',
    type: 'circle',
    source: 'cars',
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': pins.dot,
      'circle-radius': ['step', ['get', 'point_count'], 16, 4, 19, 8, 23],
      'circle-stroke-color': pins.clusterStroke,
      'circle-stroke-width': 2.5,
    },
  })
  map.addLayer({
    id: 'cluster-count',
    type: 'symbol',
    source: 'cars',
    filter: ['has', 'point_count'],
    layout: {
      'text-field': ['get', 'point_count_abbreviated'],
      'text-font': ['Noto Sans Bold'],
      'text-size': 13,
      'text-allow-overlap': true,
    },
    paint: { 'text-color': pins.clusterText },
  })

  // Невидимая увеличенная зона нажатия — по точке легко попасть пальцем.
  map.addLayer({
    id: 'car-hit',
    type: 'circle',
    source: 'cars',
    filter: unclustered,
    paint: { 'circle-radius': 18, 'circle-opacity': 0 },
  })

  const dotFade = ['interpolate', ['linear'], ['zoom'], DOTS_UNTIL, 1, CARS_FROM, 0]
  map.addLayer({
    id: 'car-dots',
    type: 'circle',
    source: 'cars',
    filter: unclustered,
    paint: {
      'circle-radius': [
        'interpolate', ['linear'], ['zoom'],
        10, ['case', ['get', 'busy'], 2.5, 3.5],
        DOTS_UNTIL, ['case', ['get', 'busy'], 5, 6.5],
      ],
      'circle-color': [
        'case',
        ['get', 'locked'], 'rgba(0,0,0,0)',
        ['get', 'busy'], pins.dotBusy,
        pins.dot,
      ],
      'circle-stroke-color': [
        'case',
        ['get', 'locked'], pins.dotLocked,
        ['get', 'premium'], pins.premiumStroke,
        pins.dotStroke,
      ],
      'circle-stroke-width': ['case', ['all', ['get', 'busy'], ['!', ['get', 'locked']]], 0, 2],
      'circle-opacity': dotFade,
      'circle-stroke-opacity': dotFade,
    },
  })
  // Шампань-сердцевина у машин Signature — ливрею видно даже на общем плане.
  map.addLayer({
    id: 'car-dots-core',
    type: 'circle',
    source: 'cars',
    filter: ['all', unclustered, ['get', 'signature'], ['!', ['get', 'locked']], ['!', ['get', 'busy']]],
    paint: { 'circle-radius': 2.2, 'circle-color': pins.signatureCore, 'circle-opacity': dotFade },
  })

  map.addLayer({
    id: 'car-icons',
    type: 'symbol',
    source: 'cars',
    filter: unclustered,
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-rotate': ['get', 'angle'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      'icon-size': ICON_SIZE,
    },
    paint: {
      'icon-opacity': [
        'interpolate', ['linear'], ['zoom'],
        DOTS_UNTIL, 0,
        CARS_FROM, ['case', ['any', ['get', 'busy'], ['get', 'locked']], 0.42, 1],
      ],
    },
  })
  map.addLayer({
    id: 'car-price',
    type: 'symbol',
    source: 'cars',
    filter: unclustered,
    minzoom: 15.5,
    layout: {
      'text-field': ['concat', ['get', 'price'], ' BYN'],
      'text-font': ['Noto Sans Bold'],
      'text-size': 11.5,
      'text-anchor': 'bottom',
      'text-offset': [0, -3],
      'text-allow-overlap': true,
      'icon-image': 'pill-dark',
      'icon-text-fit': 'both',
      'icon-text-fit-padding': [3, 8, 3, 8],
      'icon-allow-overlap': true,
    },
    paint: { 'text-color': pins.priceText },
  })

  // Выбранная машина: всегда силуэтом, с кольцом и ивори-зазором, на любом зуме.
  const ringRadius = ['interpolate', ['linear'], ['zoom'], 11, 14, 15, 30, 18, 58]
  map.addLayer({
    id: 'selected-halo',
    type: 'circle',
    source: 'selected',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 22, 15, 42, 18, 72],
      'circle-color': pins.halo,
      'circle-opacity': 0.2,
      'circle-blur': 0.6,
    },
  })
  map.addLayer({
    id: 'selected-ring',
    type: 'circle',
    source: 'selected',
    paint: {
      'circle-radius': ringRadius,
      'circle-color': 'rgba(0,0,0,0)',
      'circle-stroke-color': pins.selectedGap,
      'circle-stroke-width': 2,
    },
  })
  map.addLayer({
    id: 'selected-ring-outer',
    type: 'circle',
    source: 'selected',
    paint: {
      // zoom допустим только на верхнем уровне interpolate — поэтому отдельная шкала, а не ringRadius + 2.
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 16, 15, 32, 18, 60],
      'circle-color': 'rgba(0,0,0,0)',
      'circle-stroke-color': pins.selectedRing,
      'circle-stroke-width': 2,
    },
  })
  map.addLayer({
    id: 'selected-icon',
    type: 'symbol',
    source: 'selected',
    layout: {
      'icon-image': ['get', 'icon'],
      'icon-rotate': ['get', 'angle'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      'icon-size': ['interpolate', ['linear'], ['zoom'], 9, 0.5, 15, 0.92, 17.5, 1.38],
    },
  })
  map.addLayer({
    id: 'selected-price',
    type: 'symbol',
    source: 'selected',
    minzoom: 13,
    layout: {
      'text-field': ['concat', ['get', 'price'], ' BYN/мин'],
      'text-font': ['Noto Sans Bold'],
      'text-size': 12,
      'text-anchor': 'bottom',
      'text-offset': [0, -3.4],
      'text-allow-overlap': true,
      'icon-image': 'pill-gold',
      'icon-text-fit': 'both',
      'icon-text-fit-padding': [4, 9, 4, 9],
      'icon-allow-overlap': true,
    },
    paint: { 'text-color': pins.priceSelectedText },
  })
}

/** Отступы камеры: на компьютере панель слева, на телефоне — шторка снизу. */
export function panelPadding(map) {
  const box = map.getContainer().getBoundingClientRect()
  const panel = document.querySelector('.map-panel')
  const top = Math.min(170, box.height * 0.25)
  if (!panel) return { top, bottom: 60, left: 60, right: 70 }
  const rect = panel.getBoundingClientRect()
  if (rect.width < box.width * 0.55) {
    return { top: 110, bottom: 60, left: Math.max(60, rect.right - box.left + 40), right: 80 }
  }
  const covered = Math.max(0, box.bottom - rect.top)
  return { top, bottom: Math.max(60, Math.min(covered + 30, box.height - top - 120)), left: 40, right: 60 }
}

/** Маршрут ведёт именно к этой машине (последняя точка линии — её координаты). */
function routeLeadsTo(route, car) {
  const last = route?.geometry?.[route.geometry.length - 1]
  return Boolean(
    last && Math.abs(last[0] - car.longitude) < 1e-4 && Math.abs(last[1] - car.latitude) < 1e-4,
  )
}

function destinationElement() {
  const element = document.createElement('div')
  element.className = 'dest-pin'
  element.innerHTML = '<span>Сюда</span>'
  return element
}

function etaElement(route) {
  const { time, distance } = formatWalk(route)
  const element = document.createElement('div')
  element.className = 'map-eta'
  const approx = route.source === 'estimate' ? '≈ ' : ''
  element.innerHTML = `${WALK_SVG}<b>${approx}${time}</b><span>${distance}</span>`
  return element
}

export default function CarMap({
  cars: allCars,
  selectedId = null,
  onSelect = () => {},
  interactive = true,
  userLocation = null,
  route = null,
  onLocate,
  onSetLocation,
  onRefresh,
  refreshing = false,
  fitKey = '',
  theme = 'night',
  destination = null,
  tripRoute = null,
  picking = false,
  onPickPoint,
}) {
  const cars = useMemo(() => allCars.filter(hasValidPosition), [allCars])
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const carsRef = useRef(cars)
  const handlersRef = useRef({ onSelect, onSetLocation, onPickPoint, picking })
  const destMarkerRef = useRef(null)
  const userMarkerRef = useRef(null)
  const etaMarkerRef = useRef(null)
  const firstFitRef = useRef(true)
  const cameraKeyRef = useRef('')
  const fittedKeyRef = useRef(undefined)
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(false)

  carsRef.current = cars
  handlersRef.current = { onSelect, onSetLocation, onPickPoint, picking }

  useEffect(() => {
    let cancelled = false
    let map = null

    loadMapStyle(theme)
      .then((style) => {
        if (cancelled || !containerRef.current) return
        map = new maplibregl.Map({
          container: containerRef.current,
          style,
          center: MINSK,
          zoom: 12,
          minZoom: 9,
          maxZoom: 18.5,
          interactive,
          attributionControl: false,
          dragRotate: false,
          pitchWithRotate: false,
          touchPitch: false,
        })
        map.touchZoomRotate?.disableRotation()
        map.addControl(
          new maplibregl.AttributionControl({ compact: true, customAttribution: ROUTING_CREDIT }),
          'bottom-right',
        )
        mapRef.current = map

        map.on('load', () => {
          addLayers(map, pinPalette(theme))
          if (interactive) {
            map.on('click', (event) => {
              // Режим «укажите, куда едем»: нажатие ставит точку назначения, машины не выбираются.
              if (handlersRef.current.picking) {
                handlersRef.current.onPickPoint?.(event.lngLat.lat, event.lngLat.lng)
                return
              }
              const [cluster] = map.queryRenderedFeatures(event.point, { layers: ['clusters'] })
              if (cluster) {
                map
                  .getSource('cars')
                  .getClusterExpansionZoom(cluster.properties.cluster_id)
                  .then((zoom) => map.easeTo({ center: cluster.geometry.coordinates, zoom: zoom + 0.5 }))
                return
              }
              const [feature] = map.queryRenderedFeatures(event.point, { layers: CLICKABLE })
              const car = feature && carsRef.current.find((item) => item.id === feature.properties.id)
              handlersRef.current.onSelect(car || null)
            })
            ;[...CLICKABLE, 'clusters'].forEach((layer) => {
              map.on('mouseenter', layer, () => (map.getCanvas().style.cursor = 'pointer'))
              map.on('mouseleave', layer, () => (map.getCanvas().style.cursor = ''))
            })
            map.on('contextmenu', (event) => {
              handlersRef.current.onSetLocation?.(event.lngLat.lat, event.lngLat.lng)
            })
          }
          setReady(true)
        })
      })
      .catch(() => !cancelled && setFailed(true))

    return () => {
      cancelled = true
      map?.remove()
      mapRef.current = null
    }
    // Тема меняется ключом компонента: карта создаётся заново со своей палитрой.
  }, [interactive])

  // В режиме выбора точки — прицел вместо руки.
  useEffect(() => {
    const canvas = mapRef.current?.getCanvas()
    if (canvas) canvas.style.cursor = picking ? 'crosshair' : ''
  }, [ready, picking])

  // Точка назначения и маршрут поездки на машине.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    const coordinates = tripRoute?.geometry || []
    map.getSource('trip')?.setData(
      coordinates.length > 1
        ? { type: 'Feature', geometry: { type: 'LineString', coordinates }, properties: {} }
        : EMPTY,
    )
    if (!destination) {
      destMarkerRef.current?.remove()
      destMarkerRef.current = null
      return
    }
    const point = [destination.lng, destination.lat]
    if (!destMarkerRef.current) {
      destMarkerRef.current = new maplibregl.Marker({ element: destinationElement(), anchor: 'bottom' })
        .setLngLat(point)
        .addTo(map)
    } else {
      destMarkerRef.current.setLngLat(point)
    }
    if (coordinates.length > 1) {
      const bounds = coordinates.reduce(
        (box, item) => box.extend(item),
        new maplibregl.LngLatBounds(coordinates[0], coordinates[0]),
      )
      if (userLocation) bounds.extend([userLocation.lng, userLocation.lat])
      map.fitBounds(bounds, { padding: panelPadding(map), maxZoom: 15, duration: 900 })
    } else {
      map.easeTo({ center: point, zoom: Math.max(map.getZoom(), 13), duration: 600 })
    }
  }, [ready, destination?.lat, destination?.lng, tripRoute])

  // Машины и выбранная машина — отдельные источники: выбранная не попадает в кластер.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return undefined
    let stale = false
    ensureCarImages(map, cars).then(() => {
      if (stale || !map.getSource('cars')) return
      const others = cars.filter((car) => car.id !== selectedId).map((car) => toFeature(car, selectedId))
      const chosen = cars.filter((car) => car.id === selectedId).map((car) => toFeature(car, selectedId))
      map.getSource('cars').setData(collection(others))
      map.getSource('selected').setData(collection(chosen))
    })
    return () => {
      stale = true
    }
  }, [ready, cars, selectedId])

  // «Дышащий» ореол выбранной машины.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !selectedId) return undefined
    let frame = 0
    const tick = (time) => {
      const phase = (Math.sin((time / 2400) * Math.PI * 2) + 1) / 2
      if (map.getLayer('selected-halo')) {
        map.setPaintProperty('selected-halo', 'circle-opacity', 0.2 + phase * 0.25)
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [ready, selectedId])

  // Подгоняем камеру под выборку машин — при первой загрузке и смене фильтров (fitKey),
  // но не когда из списка просто ушла или вернулась машина (бронь, начало поездки).
  // fitKey === null — новые данные ещё грузятся, ждём их.
  const hasCars = cars.length > 0
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !hasCars || fitKey === null || fittedKeyRef.current === fitKey) return
    fittedKeyRef.current = fitKey
    // Если машина уже выбрана (например, своя бронь), камерой управляет выбор.
    if (interactive && selectedId) return
    const bounds = new maplibregl.LngLatBounds()
    cars.forEach((car) => bounds.extend([car.longitude, car.latitude]))
    if (interactive && userLocation) bounds.extend([userLocation.lng, userLocation.lat])
    map.fitBounds(bounds, {
      padding: interactive ? { top: 90, bottom: 60, left: 60, right: 80 } : 40,
      maxZoom: interactive ? 14 : 15.5,
      duration: firstFitRef.current ? 0 : 700,
    })
    firstFitRef.current = false
  }, [ready, hasCars, fitKey])

  // Камера при выборе: весь пеший путь, если он уже построен до этой машины, иначе — сама машина.
  // Одно место решения — иначе «подлёт к машине» и «весь маршрут» спорят, кто сработает последним.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !interactive) return
    const car = cars.find((item) => item.id === selectedId)
    if (!car) {
      cameraKeyRef.current = ''
      return
    }
    const withRoute = routeLeadsTo(route, car)
    const key = withRoute ? `${car.id}:${route.geometry[0].join(',')}` : `${car.id}:car`
    if (cameraKeyRef.current === key) return
    cameraKeyRef.current = key

    requestAnimationFrame(() => {
      if (withRoute) {
        const bounds = route.geometry.reduce(
          (box, point) => box.extend(point),
          new maplibregl.LngLatBounds(route.geometry[0], route.geometry[0]),
        )
        map.fitBounds(bounds, { padding: panelPadding(map), maxZoom: 16.5, duration: 800 })
      } else {
        map.easeTo({
          center: [car.longitude, car.latitude],
          zoom: Math.max(map.getZoom(), 15),
          padding: panelPadding(map),
          duration: 700,
        })
      }
    })
  }, [ready, selectedId, route, cars])

  // Маршрут пешком и плашка со временем в его середине.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    const coordinates = route?.geometry || []
    map.getSource('route')?.setData(
      coordinates.length > 1
        ? { type: 'Feature', geometry: { type: 'LineString', coordinates }, properties: {} }
        : EMPTY,
    )

    etaMarkerRef.current?.remove()
    etaMarkerRef.current = null
    if (coordinates.length < 2) return

    // У прямой линии из двух точек «середина» — это сама машина: берём среднюю точку отрезка.
    const middle =
      coordinates.length === 2
        ? [(coordinates[0][0] + coordinates[1][0]) / 2, (coordinates[0][1] + coordinates[1][1]) / 2]
        : coordinates[Math.floor(coordinates.length / 2)]
    etaMarkerRef.current = new maplibregl.Marker({ element: etaElement(route) }).setLngLat(middle).addTo(map)
  }, [ready, route])

  // Метка клиента.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !userLocation || !interactive) return
    const point = [userLocation.lng, userLocation.lat]
    if (!userMarkerRef.current) {
      const element = document.createElement('div')
      element.className = 'user-dot'
      // MapLibre требует координаты до addTo, иначе маркер падает при первой отрисовке.
      userMarkerRef.current = new maplibregl.Marker({ element }).setLngLat(point).addTo(map)
    } else {
      userMarkerRef.current.setLngLat(point)
    }
  }, [ready, userLocation?.lat, userLocation?.lng, interactive])

  const flyToMe = async () => {
    const result = onLocate ? await onLocate() : null
    const point = result?.location || userLocation
    if (point && mapRef.current) {
      mapRef.current.flyTo({ center: [point.lng, point.lat], zoom: 15, duration: 900 })
    }
  }

  return (
    <div className="map-canvas">
      <div ref={containerRef} className="map-canvas__gl" />

      {failed && (
        <div className="map-fallback">
          Карта не загрузилась — нужен доступ в интернет. Список машин работает.
        </div>
      )}

      {interactive && ready && (
        <>
          <div className="map-controls">
            <button type="button" className="map-control" onClick={flyToMe} title="Где я">
              <IconLocate />
            </button>
            {onRefresh && (
              <button
                type="button"
                className={`map-control ${refreshing ? 'map-control--spin' : ''}`}
                onClick={onRefresh}
                title="Обновить"
              >
                <IconRefresh />
              </button>
            )}
          </div>
          <div className="map-controls map-controls--zoom">
            <button
              type="button"
              className="map-control"
              onClick={() => mapRef.current?.zoomIn()}
              title="Приблизить"
            >
              <IconPlus />
            </button>
            <button
              type="button"
              className="map-control"
              onClick={() => mapRef.current?.zoomOut()}
              title="Отдалить"
            >
              <IconMinus />
            </button>
          </div>
        </>
      )}
    </div>
  )
}
