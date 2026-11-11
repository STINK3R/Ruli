// Личный (идентификационный) номер паспорта и ID-карты РБ — та же проверка, что на сервере.
// 3 150589 A 001 PB 1: пол и век · дата рождения ДДММГГ · регион · порядковый номер · гражданство · контроль.

const PATTERN = /^([1-6])(\d{2})(\d{2})(\d{2})([ABCHKEM])(\d{3})([A-Z]{2})(\d)$/
const CENTURY = { 1: 1800, 2: 1800, 3: 1900, 4: 1900, 5: 2000, 6: 2000 }
const TWINS = { А: 'A', В: 'B', Е: 'E', К: 'K', М: 'M', Н: 'H', О: 'O', Р: 'P', С: 'C', Т: 'T', Х: 'X' }

export function normalizePersonalNumber(value) {
  return (value || '')
    .toUpperCase()
    .replace(/[АВЕКМНОРСТХ]/g, (char) => TWINS[char])
    .replace(/\s/g, '')
}

/** Контрольная цифра по ICAO 9303 (как в машиночитаемой зоне паспорта): веса 7, 3, 1. */
export function checkDigit(text) {
  let total = 0
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]
    const value = /\d/.test(char) ? Number(char) : char.charCodeAt(0) - 55
    total += value * [7, 3, 1][i % 3]
  }
  return total % 10
}

/** { ok, birth: 'YYYY-MM-DD', sex, message } — для подсказки прямо под полем. */
export function parsePersonalNumber(value) {
  const number = normalizePersonalNumber(value)
  if (!number) return { ok: false, message: '' }
  const match = PATTERN.exec(number)
  if (!match) {
    return { ok: false, message: number.length < 14 ? `${number.length} из 14 знаков` : 'Формат: 7 цифр, буква, 3 цифры, 2 буквы, цифра' }
  }
  if (checkDigit(number.slice(0, 13)) !== Number(number[13])) {
    return { ok: false, message: 'Контрольная цифра не сходится — проверьте номер' }
  }
  const [, sexCentury, day, month, year] = match
  const fullYear = CENTURY[sexCentury] + Number(year)
  const birth = `${fullYear}-${month}-${day}`
  const date = new Date(`${birth}T00:00:00`)
  if (Number.isNaN(date.getTime()) || date.getDate() !== Number(day)) {
    return { ok: false, message: 'В номере зашита несуществующая дата' }
  }
  return {
    ok: true,
    birth,
    sex: Number(sexCentury) % 2 === 0 ? 'f' : 'm',
    message: `Номер корректен · дата рождения ${day}.${month}.${fullYear}`,
  }
}
