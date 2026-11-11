// Растягиваемая «пилюля» под ценник: MapLibre вписывает её вокруг текста
// (icon-text-fit), а закруглённые края при растяжении не искажаются.
const SCALE = 2
const WIDTH = 48
const HEIGHT = 24
const RADIUS = 10

export function addPillImage(map, id, fill, stroke) {
  if (map.hasImage(id)) return
  const canvas = document.createElement('canvas')
  canvas.width = WIDTH * SCALE
  canvas.height = HEIGHT * SCALE
  const ctx = canvas.getContext('2d')
  ctx.scale(SCALE, SCALE)
  ctx.beginPath()
  ctx.roundRect(1, 1, WIDTH - 2, HEIGHT - 2, RADIUS)
  ctx.fillStyle = fill
  ctx.fill()
  if (stroke) {
    ctx.lineWidth = 1
    ctx.strokeStyle = stroke
    ctx.stroke()
  }
  const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height)
  map.addImage(
    id,
    { width: canvas.width, height: canvas.height, data },
    {
      pixelRatio: SCALE,
      stretchX: [[RADIUS * SCALE, (WIDTH - RADIUS) * SCALE]],
      stretchY: [[RADIUS * SCALE, (HEIGHT - RADIUS) * SCALE]],
      content: [8 * SCALE, 4 * SCALE, (WIDTH - 8) * SCALE, (HEIGHT - 4) * SCALE],
    },
  )
}
