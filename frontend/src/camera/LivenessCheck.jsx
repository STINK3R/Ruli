import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { errorCode, extractError } from '../api/client'
import { useDialogFocus } from '../components/Modal'
import { IconCheck, IconClose, IconFace, IconSpark } from '../components/icons'
import { makeDemoFaceFrames } from '../utils/demoFace'
import { useCamera } from './useCamera'

const STEP_MS = { center: 1700 }
const DEFAULT_STEP_MS = 2300
const STEP_HINTS = {
  center: 'Держите телефон на уровне глаз',
  turn_left: 'Плавно, не спеша',
  turn_right: 'Плавно, не спеша',
  look_up: 'Совсем немного',
  smile: 'Можно шире 🙂',
  closer: 'Лицо должно заполнить овал',
}

function Countdown({ duration, stepKey }) {
  return (
    <svg className="liveness__ring" viewBox="0 0 100 100" key={stepKey} aria-hidden="true">
      <circle cx="50" cy="50" r="46" />
      <circle cx="50" cy="50" r="46" className="liveness__ring-value" style={{ animationDuration: `${duration}ms` }} />
    </svg>
  )
}

function Camera({ steps, onFrames, onCancel, onDemo }) {
  const { videoRef, ready, error, capture } = useCamera('user')
  const [index, setIndex] = useState(-1)
  const frames = useRef({})

  useEffect(() => {
    if (ready && index === -1) setIndex(0)
  }, [ready, index])

  useEffect(() => {
    if (index < 0 || index >= steps.length) return undefined
    const step = steps[index]
    const timer = setTimeout(async () => {
      try {
        frames.current[step.code] = await capture({ maxSide: 960, quality: 0.88 })
      } catch {
        /* кадр не снялся — сервер попросит повторить */
      }
      if (index + 1 < steps.length) setIndex(index + 1)
      else onFrames(frames.current)
    }, STEP_MS[step.code] || DEFAULT_STEP_MS)
    return () => clearTimeout(timer)
  }, [index, steps])

  const step = steps[Math.max(0, index)]
  return (
    <div className="liveness__stage">
      <div className="liveness__view is-mirrored">
        <video ref={videoRef} playsInline muted autoPlay />
        <div className="liveness__oval">
          {index >= 0 && <Countdown duration={STEP_MS[step.code] || DEFAULT_STEP_MS} stepKey={step.code} />}
        </div>
        {error && (
          <div className="camera__error">
            <IconFace width={28} height={28} />
            <p>{error}</p>
            {onDemo && (
              <button type="button" className="btn btn--cta" onClick={onDemo}>
                <IconSpark width={16} height={16} />
                Демо-кадры для защиты
              </button>
            )}
            <button type="button" className="btn btn--ghost" onClick={onCancel}>
              Назад
            </button>
          </div>
        )}
      </div>
      {!error && (
        <div className="liveness__instruction" key={step.code} aria-live="assertive">
          <b className="tag-title">{ready ? step.label : 'Включаем камеру…'}</b>
          <span>{ready ? STEP_HINTS[step.code] : ' '}</span>
        </div>
      )}
      <ol className="liveness__dots">
        {steps.map((item, i) => (
          <li key={item.code} className={i < index ? 'is-done' : i === index ? 'is-current' : ''} />
        ))}
      </ol>
    </div>
  )
}

/**
 * Проверка «живости»: сервер выдаёт случайные движения и две минуты, приложение
 * само снимает кадр в конце каждого движения. Заранее записанное видео или фото не подойдёт.
 * start() → { id, steps, ttl_seconds }, submit(check, frames, demo) → результат.
 */
export default function LivenessCheck({ title = 'Проверка «живости»', intro, start, submit, onPassed, onClose, demoMode }) {
  const ref = useDialogFocus(onClose)
  const titleId = useId()
  const [phase, setPhase] = useState('intro')
  const [check, setCheck] = useState(null)
  const [failure, setFailure] = useState('')
  const [left, setLeft] = useState(0)

  useEffect(() => {
    if (!check || phase !== 'capture') return undefined
    const deadline = Date.now() + check.ttl_seconds * 1000
    const tick = () => setLeft(Math.max(0, Math.round((deadline - Date.now()) / 1000)))
    tick()
    const timer = setInterval(tick, 500)
    return () => clearInterval(timer)
  }, [check, phase])

  const begin = async (demo = false) => {
    setFailure('')
    setPhase('starting')
    try {
      const next = await start()
      setCheck(next)
      if (demo) send(next, await makeDemoFaceFrames(next.steps), true)
      else setPhase('capture')
    } catch (error) {
      setFailure(extractError(error, 'Не удалось начать проверку'))
      setPhase('failed')
    }
  }

  const send = async (current, frames, demo = false) => {
    setPhase('uploading')
    try {
      const result = await submit(current, frames, demo)
      setPhase('passed')
      setTimeout(() => onPassed?.(result), 1100)
    } catch (error) {
      const code = errorCode(error)
      setFailure(
        extractError(error, 'Проверка не пройдена') +
          (code === 'liveness_expired' ? '' : ' Встаньте лицом к свету и выполняйте движения плавно.'),
      )
      setPhase('failed')
    }
  }

  return createPortal(
    <div className="camera liveness" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={ref} tabIndex={-1}>
      <header className="camera__top">
        <div>
          <h2 id={titleId}>{title}</h2>
          <p>{phase === 'capture' ? `Осталось ${left} с — следуйте подсказкам` : 'Около 10 секунд перед фронтальной камерой'}</p>
        </div>
        <button type="button" className="sheet__close" onClick={onClose} aria-label="Закрыть">
          <IconClose width={16} height={16} />
        </button>
      </header>

      {phase === 'capture' && check ? (
        <Camera
          steps={check.steps}
          onFrames={(frames) => send(check, frames)}
          onCancel={() => setPhase('intro')}
          onDemo={demoMode ? async () => send(check, await makeDemoFaceFrames(check.steps), true) : null}
        />
      ) : (
        <div className="liveness__panel">
          {phase === 'passed' ? (
            <div className="liveness__result liveness__result--ok">
              <span className="liveness__badge"><IconCheck width={40} height={40} strokeWidth={3} /></span>
              <h3 className="display">Это вы!</h3>
              <p>Кадры сохранены для модератора.</p>
            </div>
          ) : phase === 'starting' || phase === 'uploading' ? (
            <div className="liveness__result">
              <span className="spray-loader" />
              <p>{phase === 'starting' ? 'Сервер выбирает движения…' : 'Проверяем кадры…'}</p>
            </div>
          ) : (
            <div className="liveness__result">
              <span className="liveness__badge liveness__badge--face"><IconFace width={44} height={44} /></span>
              {phase === 'failed' ? (
                <div className="notice notice--danger">{failure}</div>
              ) : (
                intro || (
                  <ul className="liveness__rules">
                    <li>Снимите очки и шапку, лицо — к свету</li>
                    <li>Сервер попросит 2–4 случайных движения</li>
                    <li>Кадры снимаются сами, видео не записывается</li>
                  </ul>
                )
              )}
              <button type="button" className="btn btn--cta btn--lg btn--block" onClick={() => begin(false)}>
                {phase === 'failed' ? 'Попробовать снова' : 'Включить камеру'}
              </button>
              {demoMode && (
                <button type="button" className="btn btn--ghost btn--block" onClick={() => begin(true)}>
                  <IconSpark width={16} height={16} />
                  Демо-кадры (для защиты, без камеры)
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>,
    document.body,
  )
}
