// Фото с современного телефона весят 6–9 МБ: четыре ракурса не пролезут в лимит запроса.
// Уменьшаем в браузере до размера, который сервер всё равно оставил бы (длинная сторона 1600 px).
const MAX_SIDE_PX = 1600

/**
 * JPEG с длинной стороной не больше maxSide. Поворот по EXIF применяется здесь же:
 * после перекодирования EXIF теряется и сервер уже не сможет развернуть снимок.
 * Если файл и так небольшой или браузер не умеет его декодировать — возвращаем как есть.
 */
export async function downscaleImage(file, { maxSide = MAX_SIDE_PX, quality = 0.88, minBytes = 0 } = {}) {
  if (!file?.type?.startsWith('image/') || file.size <= minBytes || typeof createImageBitmap !== 'function') {
    return file
  }
  let bitmap
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  } catch {
    return file
  }
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
  if (scale === 1 && file.type === 'image/jpeg') {
    bitmap.close?.()
    return file
  }
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close?.()
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
  if (!blob) return file
  const name = file.name.replace(/\.[^.]+$/, '') || 'photo'
  return new File([blob], `${name}.jpg`, { type: 'image/jpeg' })
}
