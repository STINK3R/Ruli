/** Минуты пешком, не меньше одной. */
export function walkMinutes(walk) {
  return walk ? Math.max(1, Math.round(walk.duration_s / 60)) : null
}

/** Крупное число и единица для колонки списка: «7 мин» или «1:50 ч». */
export function walkParts(walk) {
  const minutes = walkMinutes(walk)
  if (minutes == null) return { value: '', unit: '' }
  if (minutes < 60) return { value: String(minutes), unit: 'мин' }
  return { value: `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`, unit: 'ч' }
}

/** «7 мин» / «1 ч 50 мин» и «550 м» / «1,2 км» для пешего пути до машины. */
export function formatWalk(walk) {
  if (!walk) return { time: '', distance: '' }
  const minutes = walkMinutes(walk)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  const time = minutes < 60 ? `${minutes} мин` : rest ? `${hours} ч ${rest} мин` : `${hours} ч`
  const distance =
    walk.distance_m < 1000
      ? `${Math.round(walk.distance_m / 10) * 10} м`
      : `${(walk.distance_m / 1000).toFixed(1).replace('.', ',')} км`
  return { time, distance }
}
