// Демо-фото документов для защиты курсовой: рисуются на canvas и проходят
// ту же серверную обработку (проверка формата, размера, очистка EXIF), что и настоящие.
export const DOCUMENT_KINDS = [
  {
    kind: 'license_front',
    label: 'Права — лицевая сторона',
    hint: 'Целиком, без бликов: видны ФИО, даты 4a/4b и номер',
  },
  {
    kind: 'license_back',
    label: 'Права — оборот',
    hint: 'Таблица категорий: строка B с датой открытия',
  },
  {
    kind: 'passport_main',
    label: 'Паспорт или ID-карта',
    hint: 'Разворот с фото. Серию и номер можно закрыть пальцем',
  },
  {
    kind: 'selfie_with_license',
    label: 'Селфи с правами',
    hint: 'Лицо и права в руке, снимок сделан сегодня',
  },
]

const formatDate = (value) => (value ? value.split('-').reverse().join('.') : '__.__.____')

function noise(ctx, width, height, amount = 22) {
  const frame = ctx.getImageData(0, 0, width, height)
  for (let i = 0; i < frame.data.length; i += 4) {
    const delta = (Math.random() - 0.5) * amount
    frame.data[i] += delta
    frame.data[i + 1] += delta
    frame.data[i + 2] += delta
  }
  ctx.putImageData(frame, 0, 0)
}

function card(ctx, x, y, width, height, color) {
  ctx.save()
  ctx.shadowColor = 'rgba(0,0,0,0.35)'
  ctx.shadowBlur = 40
  ctx.shadowOffsetY = 14
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.roundRect(x, y, width, height, 28)
  ctx.fill()
  ctx.restore()
}

function face(ctx, x, y, scale = 1) {
  ctx.save()
  ctx.translate(x, y)
  ctx.scale(scale, scale)
  ctx.fillStyle = '#B9A58C'
  ctx.beginPath()
  ctx.ellipse(0, 0, 70, 88, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = '#3A3330'
  ctx.beginPath()
  ctx.ellipse(0, -58, 78, 44, 0, Math.PI, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = '#5B5048'
  ctx.beginPath()
  ctx.ellipse(0, 190, 150, 100, 0, Math.PI, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

function licenseFront(ctx, data, x, y, width, height) {
  card(ctx, x, y, width, height, '#F1D9DD')
  ctx.fillStyle = '#C7A2AA'
  ctx.fillRect(x, y + 70, width, 6)
  ctx.fillStyle = '#5C2A35'
  ctx.font = '700 34px sans-serif'
  ctx.fillText('ВАДЗІЦЕЛЬСКАЕ ПАСВЕДЧАННЕ', x + 40, y + 52)
  ctx.font = '700 40px sans-serif'
  ctx.fillText('BY', x + width - 100, y + 52)
  ctx.fillStyle = '#CDB7A6'
  ctx.fillRect(x + 40, y + 110, 220, 280)
  face(ctx, x + 150, y + 230, 0.9)
  const [last = 'ИВАНОВ', first = 'ИВАН'] = (data.full_name_on_document || '').toUpperCase().split(' ')
  const rows = [
    ['1.', last],
    ['2.', first],
    ['3.', formatDate(data.date_of_birth)],
    ['4a.', formatDate(data.license_issued_on)],
    ['4b.', formatDate(data.license_expires_on)],
    ['5.', data.license_number || '5AB 123456'],
    ['9.', 'B'],
  ]
  ctx.fillStyle = '#2B2326'
  rows.forEach(([label, value], index) => {
    ctx.font = '600 26px sans-serif'
    ctx.fillText(label, x + 300, y + 140 + index * 42)
    ctx.font = '700 30px sans-serif'
    ctx.fillText(value, x + 360, y + 140 + index * 42)
  })
}

function licenseBack(ctx, data, x, y, width, height) {
  card(ctx, x, y, width, height, '#F1D9DD')
  ctx.strokeStyle = '#8D6A72'
  ctx.lineWidth = 2
  const categories = ['AM', 'A1', 'A', 'B', 'C1', 'C', 'D1', 'D', 'BE']
  categories.forEach((category, index) => {
    const rowY = y + 50 + index * 40
    ctx.strokeRect(x + 40, rowY, width - 80, 40)
    ctx.fillStyle = category === 'B' ? '#2B2326' : '#9C8389'
    ctx.font = '700 24px sans-serif'
    ctx.fillText(category, x + 60, rowY + 28)
    if (category === 'B') {
      ctx.fillText(formatDate(data.category_b_since), x + 200, rowY + 28)
      ctx.fillText(formatDate(data.license_expires_on), x + 420, rowY + 28)
    }
  })
}

function passport(ctx, data, x, y, width, height) {
  card(ctx, x, y, width, height, '#E9E4D6')
  ctx.fillStyle = '#7C1F2B'
  ctx.font = '700 30px sans-serif'
  ctx.fillText('РЭСПУБЛІКА БЕЛАРУСЬ · ПАШПАРТ', x + 40, y + 56)
  ctx.fillStyle = '#C9BFA8'
  ctx.fillRect(x + 40, y + 100, 230, 290)
  face(ctx, x + 155, y + 230, 0.95)
  ctx.fillStyle = '#2B2826'
  ctx.font = '700 32px sans-serif'
  const name = (data.full_name_on_document || 'Иванов Иван').toUpperCase()
  ctx.fillText(name, x + 310, y + 150)
  ctx.font = '600 26px sans-serif'
  ctx.fillText(`Дата рождения: ${formatDate(data.date_of_birth)}`, x + 310, y + 210)
  ctx.fillText('Серия/номер: ████ ██████', x + 310, y + 260)
  ctx.font = '500 22px monospace'
  ctx.fillText('P<BLR<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<', x + 40, y + height - 40)
}

/** Файл JPEG c демо-документом — данные берутся из анкеты, чтобы модератору было что сверять. */
export function makeDemoDocument(kind, data = {}) {
  const width = 1400
  const height = 950
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')

  const table = ctx.createLinearGradient(0, 0, width, height)
  table.addColorStop(0, '#6E6457')
  table.addColorStop(1, '#4A433B')
  ctx.fillStyle = table
  ctx.fillRect(0, 0, width, height)

  if (kind === 'license_front') licenseFront(ctx, data, 230, 230, 940, 480)
  if (kind === 'license_back') licenseBack(ctx, data, 230, 230, 940, 480)
  if (kind === 'passport_main') passport(ctx, data, 180, 200, 1040, 540)
  if (kind === 'selfie_with_license') {
    ctx.fillStyle = '#8F8778'
    ctx.fillRect(0, 0, width, height)
    face(ctx, 520, 400, 2.1)
    ctx.save()
    ctx.translate(820, 520)
    ctx.rotate(-0.08)
    ctx.scale(0.5, 0.5)
    licenseFront(ctx, data, 0, 0, 940, 480)
    ctx.restore()
  }

  noise(ctx, width, height)
  return new Promise((resolve) =>
    canvas.toBlob(
      (blob) => resolve(new File([blob], `${kind}.jpg`, { type: 'image/jpeg' })),
      'image/jpeg',
      0.88,
    ),
  )
}
