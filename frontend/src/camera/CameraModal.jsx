import { useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'
import { useDialogFocus } from '../components/Modal'
import { IconCamera, IconClose, IconSpark, IconSwitchCamera } from '../components/icons'
import { useCamera } from './useCamera'

/**
 * Съёмка документа в приложении: рамка по форме документа, подсказка, снимок и проверка кадра.
 * frame: 'card' (права, ID-карта), 'page' (разворот паспорта), 'face' (селфи с правами).
 */
export default function CameraModal({ title, hint, frame = 'card', onCapture, onClose, onDemo, busy = false }) {
  const ref = useDialogFocus(onClose)
  const titleId = useId()
  const { videoRef, ready, error, facing, capture, switchCamera } = useCamera(frame === 'face' ? 'user' : 'environment')
  const [shot, setShot] = useState(null)
  const [preview, setPreview] = useState(null)
  const [flash, setFlash] = useState(false)

  useEffect(() => {
    if (!shot) {
      setPreview(null)
      return undefined
    }
    const url = URL.createObjectURL(shot)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [shot])

  const take = async () => {
    setFlash(true)
    setTimeout(() => setFlash(false), 180)
    try {
      setShot(await capture())
    } catch {
      /* камера ещё не готова — кнопка просто не сработает */
    }
  }

  return createPortal(
    <div className="camera" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={ref} tabIndex={-1}>
      <header className="camera__top">
        <div>
          <h2 id={titleId}>{title}</h2>
          {hint && <p>{hint}</p>}
        </div>
        <button type="button" className="sheet__close" onClick={onClose} aria-label="Закрыть камеру">
          <IconClose width={16} height={16} />
        </button>
      </header>

      <div className={`camera__view camera__view--${frame} ${facing === 'user' ? 'is-mirrored' : ''}`}>
        {/* Видео не размонтируется: после «Переснять» поток камеры продолжает идти в тот же элемент. */}
        <video ref={videoRef} playsInline muted autoPlay />
        {preview && <img className="camera__shot" src={preview} alt="Снимок" />}
        {!preview && <div className={`camera__frame camera__frame--${frame}`}><i /><i /><i /><i /></div>}
        {flash && <div className="camera__flash" />}
        {error && (
          <div className="camera__error">
            <IconCamera width={28} height={28} />
            <p>{error}</p>
            {onDemo && (
              <button type="button" className="btn btn--cta" disabled={busy} onClick={onDemo}>
                <IconSpark width={16} height={16} />
                Демо-снимок для защиты
              </button>
            )}
          </div>
        )}
      </div>

      <footer className="camera__bottom">
        {preview ? (
          <>
            <button type="button" className="btn btn--ghost btn--lg" disabled={busy} onClick={() => setShot(null)}>
              Переснять
            </button>
            <button type="button" className="btn btn--cta btn--lg" disabled={busy} onClick={() => onCapture(shot)}>
              {busy ? 'Загружаем…' : 'Отправить'}
            </button>
          </>
        ) : (
          <>
            {onDemo && !error ? (
              <button type="button" className="btn btn--ghost btn--sm" disabled={busy} onClick={onDemo}>
                Демо
              </button>
            ) : (
              <span />
            )}
            <button
              type="button"
              className="camera__shutter"
              disabled={!ready || busy}
              onClick={take}
              aria-label="Сделать снимок"
            >
              <span />
            </button>
            <button type="button" className="icon-btn" onClick={switchCamera} aria-label="Сменить камеру">
              <IconSwitchCamera />
            </button>
          </>
        )}
      </footer>
    </div>,
    document.body,
  )
}
