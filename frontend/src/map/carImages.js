import { carTopViewSvg } from '../utils/carVisual'

// Иконка машины зависит только от цвета кузова и ливреи, поэтому
// на весь автопарк нужно лишь несколько растровых изображений.
const loading = new Map()

export function carImageId(car) {
  return `car:${(car.color || 'серый').toLowerCase()}:${car.livery || 'none'}`
}

function rasterize(car) {
  // Рисуем в двойном размере и регистрируем с pixelRatio 2 — иконки чёткие на Retina.
  const svg = carTopViewSvg({ id: 0, color: car.color, livery: car.livery }, { width: 80 })
  return new Promise((resolve, reject) => {
    const image = new Image(80, 160)
    image.onload = () => resolve(image)
    image.onerror = reject
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  })
}

export async function ensureCarImages(map, cars) {
  const variants = new Map(cars.map((car) => [carImageId(car), car]))
  await Promise.all(
    [...variants].map(async ([id, car]) => {
      if (map.hasImage(id)) return
      if (!loading.has(id)) loading.set(id, rasterize(car))
      const image = await loading.get(id)
      if (!map.hasImage(id)) map.addImage(id, image, { pixelRatio: 2 })
    }),
  )
}
