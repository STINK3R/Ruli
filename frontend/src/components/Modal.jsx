import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { IconClose } from './icons'

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Фокус внутри окна: при открытии переходит в него, Tab не уходит на карту за подложкой,
 * при закрытии возвращается туда, откуда окно открыли.
 */
export function useDialogFocus(onClose) {
  const ref = useRef(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    const previous = document.activeElement
    ref.current?.focus()
    const onKey = (event) => {
      if (event.key === 'Escape') onCloseRef.current()
      if (event.key !== 'Tab' || !ref.current) return
      const items = [...ref.current.querySelectorAll(FOCUSABLE)]
      if (!items.length) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      previous?.focus?.()
    }
  }, [])

  return ref
}

/**
 * Окно рендерится в body через портал: внутри анимированных панелей (transform)
 * position: fixed считается от панели, и окно оказалось бы зажато в ней.
 */
export default function Modal({ title, subtitle, onClose, wide = false, children }) {
  const ref = useDialogFocus(onClose)
  const titleId = useId()

  return createPortal(
    <div className="modal-backdrop" onClick={onClose}>
      <div
        ref={ref}
        tabIndex={-1}
        className={`modal modal--panel ${wide ? 'modal--wide' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal__header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {subtitle && <p className="muted">{subtitle}</p>}
          </div>
          <button type="button" className="sheet__close" onClick={onClose} aria-label="Закрыть">
            <IconClose width={16} height={16} />
          </button>
        </header>
        {children}
      </div>
    </div>,
    document.body,
  )
}
