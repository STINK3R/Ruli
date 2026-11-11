// Демо-фото для осмотра на защите курсовой, когда под рукой нет машины.
// Это обычные изображения: сервер проверяет их яркость и резкость так же, как настоящие.
export const ANGLE_LABELS = {
  front: 'Спереди',
  rear: 'Сзади',
  left: 'Слева',
  right: 'Справа',
  interior: 'Салон',
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = reject
    image.src = src
  })
}

function addNoise(ctx, width, height) {
  const frame = ctx.getImageData(0, 0, width, height)
  const { data } = frame
  for (let i = 0; i < data.length; i += 4) {
    const delta = (Math.random() - 0.5) * 36
    data[i] += delta
    data[i + 1] += delta
    data[i + 2] += delta
  }
  ctx.putImageData(frame, 0, 0)
}

function drawInterior(ctx) {
  ctx.fillStyle = '#2B2C30'
  ctx.fillRect(0, 430, 1200, 370)
  ctx.fillStyle = '#3B3D43'
  ctx.beginPath()
  ctx.roundRect(120, 300, 960, 200, 60)
  ctx.fill()
  ctx.strokeStyle = '#16171A'
  ctx.lineWidth = 28
  ctx.beginPath()
  ctx.arc(420, 520, 140, 0, Math.PI * 2)
  ctx.stroke()
  ctx.fillStyle = '#7A7468'
  ctx.fillRect(700, 360, 260, 110)
}

export async function makeDemoPhoto(car, angle) {
  const width = 1200
  const height = 800
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')

  const ground = ctx.createLinearGradient(0, 0, 0, height)
  ground.addColorStop(0, '#DCD6CB')
  ground.addColorStop(0.6, '#C8C1B4')
  ground.addColorStop(0.61, '#716D66')
  ground.addColorStop(1, '#5A5751')
  ctx.fillStyle = ground
  ctx.fillRect(0, 0, width, height)

  if (angle === 'interior' || !car.image) {
    drawInterior(ctx)
  } else {
    const image = await loadImage(car.image)
    const scale = Math.min(980 / image.width, 520 / image.height)
    const w = image.width * scale
    const h = image.height * scale
    ctx.save()
    // Разные ракурсы: машина отражается и сдвигается, чтобы фото отличались.
    if (angle === 'right' || angle === 'rear') {
      ctx.translate(width, 0)
      ctx.scale(-1, 1)
    }
    const offset = { front: 0, rear: 40, left: -60, right: 60 }[angle] || 0
    ctx.drawImage(image, (width - w) / 2 + offset, 640 - h, w, h)
    ctx.restore()
  }

  addNoise(ctx, width, height)
  ctx.fillStyle = 'rgba(22,23,26,0.82)'
  ctx.fillRect(24, 24, 430, 56)
  ctx.fillStyle = '#F3EEE4'
  ctx.font = '600 26px "Manrope Variable", sans-serif'
  ctx.fillText(`${ANGLE_LABELS[angle]} · ${car.license_plate}`, 44, 62)

  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
  return new File([blob], `${angle}.jpg`, { type: 'image/jpeg' })
}
