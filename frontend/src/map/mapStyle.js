import { mapPalette } from '../theme'

// Векторные карты OpenFreeMap (данные OpenStreetMap, схема OpenMapTiles) —
// бесплатно и без API-ключа. Базовый стиль перекрашивается в палитру темы.
const BASE_STYLE_URL =
  import.meta.env.VITE_MAP_STYLE_URL || 'https://tiles.openfreemap.org/styles/positron'

const RUSSIAN_NAME = ['coalesce', ['get', 'name:ru'], ['get', 'name']]

function restyle(layer, c) {
  const { id, type } = layer
  const paint = (values) => ({ ...layer, paint: { ...layer.paint, ...values } })

  if (type === 'background') return paint({ 'background-color': c.land })
  if (id === 'water') return paint({ 'fill-color': c.water })
  if (id === 'waterway') return paint({ 'line-color': c.water })
  if (id === 'park' || id === 'landcover_wood') return paint({ 'fill-color': c.park })
  if (id === 'landuse_residential') return paint({ 'fill-color': c.land })
  // Здания — только вблизи: на общем плане город спокойнее, машины заметнее.
  if (id === 'building') {
    return { ...paint({ 'fill-color': c.building, 'fill-outline-color': c.roadCasing }), minzoom: 15 }
  }
  if (/motorway/.test(id)) {
    return paint({ 'line-color': /casing/.test(id) ? c.motorwayCasing : c.motorway })
  }
  if (/^railway/.test(id)) return paint({ 'line-color': c.railway })
  if (/casing/.test(id)) return paint({ 'line-color': c.roadCasing })
  if (/highway_major/.test(id)) return paint({ 'line-color': c.roadMajor })
  if (/highway_(minor|path)|road_pier/.test(id)) return paint({ 'line-color': c.roadMinor })
  if (type === 'symbol' && !/shield/.test(id)) {
    const water = /water/.test(id)
    return {
      ...paint({
        'text-color': water ? c.waterLabel : c.label,
        'text-halo-color': c.labelHalo,
        'text-halo-width': 1.5,
      }),
      layout: { ...layer.layout, 'text-field': RUSSIAN_NAME },
    }
  }
  if (type === 'fill' && /landcover|landuse/.test(id)) return paint({ 'fill-color': c.park })
  // Аэродромы и границы — без светлых пятен на тёмной карте.
  if (/aeroway/.test(id)) {
    return type === 'fill' ? paint({ 'fill-color': c.park }) : paint({ 'line-color': c.roadMinor })
  }
  if (/boundary/.test(id) && type === 'line') return paint({ 'line-color': c.railway })
  return layer
}

let basePromise = null

function loadBaseStyle() {
  if (!basePromise) {
    basePromise = fetch(BASE_STYLE_URL)
      .then((response) => {
        if (!response.ok) throw new Error(`Стиль карты недоступен: ${response.status}`)
        return response.json()
      })
      .catch((error) => {
        basePromise = null
        throw error
      })
  }
  return basePromise
}

/** Базовый стиль грузится один раз; для каждой темы — своя перекрашенная копия с русскими подписями. */
export async function loadMapStyle(theme = 'night') {
  const style = await loadBaseStyle()
  const palette = mapPalette(theme)
  return { ...style, layers: style.layers.map((layer) => restyle(layer, palette)) }
}
