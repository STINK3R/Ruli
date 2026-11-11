/** plural(2, ['отметка', 'отметки', 'отметок']) → «2 отметки». */
export function plural(number, [one, few, many]) {
  const n = Math.abs(number) % 100
  if (n >= 11 && n <= 14) return `${number} ${many}`
  const last = n % 10
  if (last === 1) return `${number} ${one}`
  if (last >= 2 && last <= 4) return `${number} ${few}`
  return `${number} ${many}`
}
