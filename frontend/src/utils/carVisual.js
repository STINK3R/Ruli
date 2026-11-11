import { THEME } from '../theme'

// light — блик по центру кузова, body — основной цвет, dark — затенённые борта.
const PALETTE = {
  белый: { light: '#FFFFFF', body: '#EEF1F5', dark: '#B9C1CD' },
  серебристый: { light: '#F1F4F8', body: '#CDD3DC', dark: '#8E97A5' },
  серый: { light: '#B4BCC8', body: '#8A93A1', dark: '#555D69' },
  чёрный: { light: '#525B6B', body: '#2C323C', dark: '#14171C' },
  черный: { light: '#525B6B', body: '#2C323C', dark: '#14171C' },
  синий: { light: '#6E9DFF', body: '#2F64E0', dark: '#173A91' },
  красный: { light: '#FF7C70', body: '#DD3B2F', dark: '#8C1F18' },
  зелёный: { light: '#5BE08F', body: '#1FA85A', dark: '#0C5E31' },
  зеленый: { light: '#5BE08F', body: '#1FA85A', dark: '#0C5E31' },
}

// Машины на парковке стоят под разными углами — угол закреплён за id,
// поэтому карта выглядит живой и не «прыгает» при перерисовке.
const ANGLES = [8, 32, 57, 74, 96, 118, 141, 163, 187, 209, 232, 254, 276, 299, 322, 344]

export function carPalette(colorName) {
  return PALETTE[(colorName || '').trim().toLowerCase()] || PALETTE.серый
}

export function carAngle(id) {
  return ANGLES[id % ANGLES.length]
}

/** «0,37 BYN» — белорусский рубль с запятой, как в местных сервисах. */
export function formatMoney(value) {
  return `${Number(value).toFixed(2).replace('.', ',')} BYN`
}

export function engineLabel(car) {
  if (!car.engine_volume) return car.fuel_type_display
  const volume = Number(car.engine_volume).toFixed(1).replace('.', ',')
  return car.horsepower ? `${volume} л · ${car.horsepower} л.с.` : `${volume} л`
}

/** Тот же расчёт, что на бэкенде: поминутно или пакеты «час»/«сутки», что выгоднее. */
export function bestTripPrice(minutes, perMinute, perHour, perDay) {
  let best = minutes * perMinute
  if (perHour) {
    const rest = minutes % 60
    best = Math.min(best, Math.floor(minutes / 60) * perHour + Math.min(rest * perMinute, perHour))
  }
  if (perDay) {
    const rest = minutes % 1440
    const restPrice = bestTripPrice(rest, perMinute, perHour)
    best = Math.min(best, Math.floor(minutes / 1440) * perDay + Math.min(restPrice, perDay))
  }
  return best
}

/** Машина в фирменной ливрее Signature. */
export function isSignature(car) {
  return Boolean(car.livery) && car.livery !== 'none'
}

/** Класс закрыт именно этому водителю (гостю показываем всё как обычно). */
export function isLocked(car) {
  const eligibility = car.eligibility || {}
  return eligibility.allowed === false && eligibility.code !== 'login_required'
}

/** Машину можно забронировать прямо сейчас. */
export function isBookable(car) {
  return car.status === 'available' && !isLocked(car)
}

/** Изображение без фона (PNG/WebP) можно «подвесить» над карточкой; фото с фоном — в рамке. */
export function isCutout(url) {
  return Boolean(url) && /\.(png|webp)($|\?)/i.test(url)
}

export function freeWaitingMinutes(rental) {
  return Math.round((new Date(rental.free_waiting_until) - new Date(rental.reserved_at)) / 60000)
}

const BODY_PATH =
  'M50 4C66 4 77.5 6.5 81.5 14.5C84.5 20.5 85.5 30 85.5 42V158C85.5 171 84.5 180 81.5 186' +
  'C77.5 193.5 66 196 50 196S22.5 193.5 18.5 186C15.5 180 14.5 171 14.5 158V42' +
  'C14.5 30 15.5 20.5 18.5 14.5C22.5 6.5 34 4 50 4Z'

/**
 * Автомобиль вид сверху в стиле карт каршеринга: объёмный кузов, тонированные
 * стёкла с бликами, зеркала, выступающие колёса и фары. У машин «Рули Signature»
 * кузов в цвете ливреи, а крыша — контрастная, с монограммой «Р».
 */
export function carTopViewSvg(car, { width = 40, livery = car.livery || 'none' } = {}) {
  const signature = THEME.livery[livery]
  const { light, body, dark } = signature || carPalette(car.color)
  const roofFrom = signature ? signature.roof : light
  const roofTo = signature ? signature.roofDark : body
  const mirror = signature ? signature.mirror : dark
  const uid = `c${car.id}w${width}${livery}`
  // Signature — «тег» на крыше: буква Р баллончиком с потёками и розовой тенью.
  const monogram = signature
    ? `<g stroke-linecap="round" stroke-linejoin="round" fill="none">
    <path d="M45.5 120V100h6c4 0 6.4 2.3 6.4 5.6s-2.4 5.6-6.4 5.6h-6" stroke="${signature.tag}" stroke-width="4.4" transform="translate(1.4 1.4)"/>
    <path d="M45.5 120V100h6c4 0 6.4 2.3 6.4 5.6s-2.4 5.6-6.4 5.6h-6" stroke="${signature.mono}" stroke-width="4.4"/>
    <path d="M45.5 121v6M51 112v8M56.6 109v4" stroke="${signature.mono}" stroke-width="1.6"/>
  </g>`
    : `<path d="M31 92H45" stroke="#FFFFFF" stroke-opacity="0.35" stroke-width="2" stroke-linecap="round"/>`

  return `<svg width="${width}" height="${width * 2}" viewBox="0 0 100 200" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="b-${uid}" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0" stop-color="${dark}"/>
      <stop offset="0.2" stop-color="${body}"/>
      <stop offset="0.48" stop-color="${light}"/>
      <stop offset="0.8" stop-color="${body}"/>
      <stop offset="1" stop-color="${dark}"/>
    </linearGradient>
    <linearGradient id="r-${uid}" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="${roofFrom}"/>
      <stop offset="1" stop-color="${roofTo}"/>
    </linearGradient>
    <linearGradient id="g-${uid}" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#3A4A63"/>
      <stop offset="0.5" stop-color="#1C2533"/>
      <stop offset="1" stop-color="#0E131B"/>
    </linearGradient>
    <clipPath id="k-${uid}"><path d="${BODY_PATH}"/></clipPath>
  </defs>

  <rect x="10.5" y="36" width="10" height="28" rx="4.5" fill="#101317"/>
  <rect x="79.5" y="36" width="10" height="28" rx="4.5" fill="#101317"/>
  <rect x="10.5" y="136" width="10" height="28" rx="4.5" fill="#101317"/>
  <rect x="79.5" y="136" width="10" height="28" rx="4.5" fill="#101317"/>

  <path d="M15.5 66 7.6 63.4C5 62.6 3.6 64.4 4.3 66.8l1.2 3.6c.6 1.9 2.3 2.5 4.1 1.9L15.8 70Z" fill="${mirror}"/>
  <path d="M84.5 66l7.9-2.6c2.6-.8 4 1 3.3 3.4l-1.2 3.6c-.6 1.9-2.3 2.5-4.1 1.9L84.2 70Z" fill="${mirror}"/>

  <path d="${BODY_PATH}" fill="url(#b-${uid})" stroke="#16171A" stroke-opacity="0.55" stroke-width="1.4"/>

  <g clip-path="url(#k-${uid})">
    <path d="M30 18C29 32 29.5 44 31 56M70 18C71 32 70.5 44 69 56" stroke="${dark}" stroke-opacity="0.35" stroke-width="1.2" stroke-linecap="round"/>
    <path d="M28 170C40 174 60 174 72 170" stroke="${dark}" stroke-opacity="0.3" stroke-width="1.2" stroke-linecap="round"/>
  </g>

  <path d="M21 60C32 53.5 68 53.5 79 60L73.5 85C60 81.5 40 81.5 26.5 85Z" fill="url(#g-${uid})"/>
  <path d="M28 61.5 45 57.6 37.5 80.5 28.6 82Z" fill="#FFFFFF" opacity="0.13"/>

  <path d="M19.6 66 25.6 87V136L20.2 150C18.7 132 18.6 84 19.6 66Z" fill="url(#g-${uid})"/>
  <path d="M80.4 66 74.4 87V136L79.8 150C81.3 132 81.4 84 80.4 66Z" fill="url(#g-${uid})"/>

  <rect x="26.5" y="85" width="47" height="52" rx="7" fill="url(#r-${uid})" stroke="#16171A" stroke-opacity="0.25"/>
  ${monogram}

  <path d="M26.5 137C40 140.5 60 140.5 73.5 137L77 154C64 159.5 36 159.5 23 154Z" fill="url(#g-${uid})"/>
  <path d="M31 140.5 41 141.6 38 154.6 30 153.4Z" fill="#FFFFFF" opacity="0.1"/>

  <path d="M19.5 15C23 10 30 7.6 37 7.2L36.4 11.4C30 12 25 14.4 21.6 18.2Z" fill="#F4FAFF"/>
  <path d="M80.5 15C77 10 70 7.6 63 7.2L63.6 11.4C70 12 75 14.4 78.4 18.2Z" fill="#F4FAFF"/>
  <path d="M19.5 185C23 190 30 192.4 37 192.8L36.4 188.6C30 188 25 185.6 21.6 181.8Z" fill="#FF3B30"/>
  <path d="M80.5 185C77 190 70 192.4 63 192.8L63.6 188.6C70 188 75 185.6 78.4 181.8Z" fill="#FF3B30"/>
</svg>`
}
