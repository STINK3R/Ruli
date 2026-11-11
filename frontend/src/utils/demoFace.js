// Демо-кадры проверки «живости» для защиты без веб-камеры: нарисованное лицо
// выполняет те же движения, что просит сервер. Кадры помечаются как демо.

const POSES = {
  center: { dx: 0, dy: 0, scale: 1, turn: 0, smile: 0.2 },
  turn_left: { dx: -70, dy: 0, scale: 1, turn: -0.45, smile: 0.2 },
  turn_right: { dx: 70, dy: 0, scale: 1, turn: 0.45, smile: 0.2 },
  look_up: { dx: 0, dy: -60, scale: 1, turn: 0, smile: 0.2 },
  smile: { dx: 0, dy: 0, scale: 1, turn: 0, smile: 1 },
  closer: { dx: 0, dy: 10, scale: 1.35, turn: 0, smile: 0.2 },
}

function drawFrame(code) {
  const pose = POSES[code] || POSES.center
  const canvas = document.createElement('canvas')
  canvas.width = 640
  canvas.height = 480
  const ctx = canvas.getContext('2d')

  const wall = ctx.createLinearGradient(0, 0, 640, 480)
  wall.addColorStop(0, '#2a3a8f')
  wall.addColorStop(1, '#141b45')
  ctx.fillStyle = wall
  ctx.fillRect(0, 0, 640, 480)

  ctx.save()
  ctx.translate(320 + pose.dx, 250 + pose.dy)
  ctx.scale(pose.scale * (1 - Math.abs(pose.turn) * 0.25), pose.scale)

  ctx.fillStyle = '#1b1c22' // волосы и плечи
  ctx.beginPath()
  ctx.ellipse(0, 210, 190, 90, 0, Math.PI, 0)
  ctx.fill()
  ctx.beginPath()
  ctx.ellipse(0, -40, 112, 130, 0, 0, Math.PI * 2)
  ctx.fill()

  ctx.fillStyle = '#d9a982'
  ctx.beginPath()
  ctx.ellipse(0, 0, 98, 124, 0, 0, Math.PI * 2)
  ctx.fill()

  const eyeShift = pose.turn * 40
  ctx.fillStyle = '#26211f'
  ;[-36, 36].forEach((x) => {
    ctx.beginPath()
    ctx.ellipse(x + eyeShift, -18, 11, 7, 0, 0, Math.PI * 2)
    ctx.fill()
  })
  ctx.strokeStyle = '#8a4b3c'
  ctx.lineWidth = 6
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.arc(eyeShift * 0.8, 40, 26 + pose.smile * 14, 0.15 * Math.PI, 0.85 * Math.PI)
  ctx.stroke()
  ctx.restore()

  // Шум камеры — каждый кадр немного отличается, как в жизни.
  const image = ctx.getImageData(0, 0, 640, 480)
  for (let i = 0; i < image.data.length; i += 4) {
    const noise = (Math.random() - 0.5) * 14
    image.data[i] += noise
    image.data[i + 1] += noise
    image.data[i + 2] += noise
  }
  ctx.putImageData(image, 0, 0)

  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
}

export async function makeDemoFaceFrames(steps) {
  const frames = {}
  for (const step of steps) frames[step.code] = await drawFrame(step.code)
  return frames
}
