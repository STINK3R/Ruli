import { useCallback, useEffect, useRef, useState } from 'react'

const ERRORS = {
  NotAllowedError: 'Нет доступа к камере — разрешите его в настройках браузера.',
  NotFoundError: 'Камера не найдена.',
  NotReadableError: 'Камера занята другим приложением.',
  OverconstrainedError: 'Эта камера не подходит — попробуйте другую.',
  SecurityError: 'Камера работает только по HTTPS или на localhost.',
}

/**
 * Живая камера в элементе <video>. Снимок — только с камеры, не из галереи:
 * так в заявку не попадёт старое или чужое фото.
 */
export function useCamera(initialFacing = 'environment') {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [facing, setFacing] = useState(initialFacing)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setReady(false)
    setError(null)

    if (!navigator.mediaDevices?.getUserMedia) {
      setError(window.isSecureContext ? 'Браузер не умеет работать с камерой.' : ERRORS.SecurityError)
      return undefined
    }

    navigator.mediaDevices
      .getUserMedia({
        audio: false,
        video: { facingMode: { ideal: facing }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }
        streamRef.current = stream
        const video = videoRef.current
        if (video) {
          video.srcObject = stream
          video.onloadedmetadata = () => {
            video.play().catch(() => {})
            setReady(true)
          }
        }
      })
      .catch((reason) => !cancelled && setError(ERRORS[reason?.name] || 'Не удалось включить камеру.'))

    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
  }, [facing])

  /** Кадр с камеры в JPEG. mirror — для фронтальной камеры, чтобы снимок совпадал с превью. */
  const capture = useCallback(
    ({ maxSide = 1600, quality = 0.9 } = {}) =>
      new Promise((resolve, reject) => {
        const video = videoRef.current
        if (!video || !video.videoWidth) {
          reject(new Error('Камера ещё не готова'))
          return
        }
        const scale = Math.min(1, maxSide / Math.max(video.videoWidth, video.videoHeight))
        const canvas = document.createElement('canvas')
        canvas.width = Math.round(video.videoWidth * scale)
        canvas.height = Math.round(video.videoHeight * scale)
        const ctx = canvas.getContext('2d')
        if (facing === 'user') {
          ctx.translate(canvas.width, 0)
          ctx.scale(-1, 1)
        }
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
        canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Снимок не получился'))), 'image/jpeg', quality)
      }),
    [facing],
  )

  const switchCamera = useCallback(() => setFacing((value) => (value === 'user' ? 'environment' : 'user')), [])

  return { videoRef, ready, error, facing, capture, switchCamera }
}
