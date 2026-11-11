import { createContext, useCallback, useContext, useId, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useDialogFocus } from '../components/Modal'
import { IconAlert, IconCheck, IconClose, IconInfo, IconSeal } from '../components/icons'
import Splash from '../components/Splash'
import { formatMoney } from '../utils/carVisual'

const UiContext = createContext(null)

const TOAST_ICONS = {
  success: <IconCheck width={15} height={15} strokeWidth={2.6} />,
  info: <IconInfo width={15} height={15} />,
  error: <IconAlert width={15} height={15} />,
}

function TripSummary({ rental, onClose }) {
  const ref = useDialogFocus(onClose)
  const titleId = useId()

  const waiting = Number(rental.waiting_cost || 0)
  const seals = rental.inspections || []
  const rewards = rental.rewards || []
  const earned = rewards.reduce((sum, item) => sum + item.amount, 0)

  return createPortal(
    <div className="modal-backdrop" onClick={onClose}>
      <div
        ref={ref}
        tabIndex={-1}
        className="modal modal--receipt"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal__check">
          <IconCheck width={28} height={28} strokeWidth={2.4} />
          {rewards.length > 0 && <Splash />}
        </div>
        <h2 className="display" id={titleId}>
          Поездка завершена
        </h2>
        <p className="muted">
          {rental.car.title} · {rental.car.license_plate}
        </p>

        <div className="receipt">
          <div className="receipt__row">
            <span>Поездка · {rental.duration_minutes} мин</span>
            <span>{formatMoney(rental.trip_cost)}</span>
          </div>
          {rental.compensation_minutes > 0 && (
            <div className="receipt__row receipt__row--gift">
              <span>Гарантия Signature</span>
              <span>−{rental.compensation_minutes} мин</span>
            </div>
          )}
          <div className="receipt__row">
            <span>Платное ожидание</span>
            <span>{waiting > 0 ? formatMoney(waiting) : 'бесплатно'}</span>
          </div>
          {rental.points_spent > 0 && (
            <div className="receipt__row receipt__row--gift">
              <span>Баллами · {rental.points_spent}</span>
              <span>−{formatMoney(rental.points_discount)}</span>
            </div>
          )}
          <div className="receipt__row receipt__row--total">
            <span>Итого</span>
            <span>{formatMoney(rental.total_cost)}</span>
          </div>
        </div>

        {rewards.length > 0 && (
          <div className="receipt__rewards">
            <span className="sticker sticker--pink">+{earned} в Движ</span>
            <ul>
              {rewards.map((item) => (
                <li key={item.title}>
                  <span>{item.title}</span>
                  <b>+{item.amount}</b>
                </li>
              ))}
            </ul>
          </div>
        )}

        {seals.length > 0 && (
          <div className="receipt__seals">
            {seals.map((inspection) => (
              <span key={inspection.id} className="seal-chip">
                <IconSeal width={12} height={12} />
                {inspection.kind_display} #{inspection.seal_short}
              </span>
            ))}
          </div>
        )}

        <button className="btn btn--cta btn--lg btn--block" onClick={onClose}>
          Готово
        </button>
      </div>
    </div>,
    document.body,
  )
}

export function UiProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const [summary, setSummary] = useState(null)
  const nextId = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((toast) => toast.id !== id))
  }, [])

  const notify = useCallback(
    (title, { description, tone = 'success', duration = 4500 } = {}) => {
      nextId.current += 1
      const id = nextId.current
      setToasts((list) => [...list.slice(-2), { id, title, description, tone }])
      setTimeout(() => dismiss(id), duration)
    },
    [dismiss],
  )

  const closeSummary = useCallback(() => setSummary(null), [])
  const value = useMemo(() => ({ notify, showTripSummary: setSummary }), [notify])

  return (
    <UiContext.Provider value={value}>
      {children}

      <div className="toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast--${toast.tone}`}>
            <span className="toast__icon">{TOAST_ICONS[toast.tone] || TOAST_ICONS.success}</span>
            <div className="toast__body">
              <div className="toast__title">{toast.title}</div>
              {toast.description && <div className="toast__text">{toast.description}</div>}
            </div>
            <button className="toast__close" onClick={() => dismiss(toast.id)} aria-label="Закрыть">
              <IconClose width={14} height={14} />
            </button>
          </div>
        ))}
      </div>

      {summary && <TripSummary rental={summary} onClose={closeSummary} />}
    </UiContext.Provider>
  )
}

export function useUi() {
  const context = useContext(UiContext)
  if (!context) throw new Error('useUi используется вне UiProvider')
  return context
}
