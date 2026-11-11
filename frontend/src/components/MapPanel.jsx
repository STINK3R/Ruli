import { useEffect, useLayoutEffect, useRef, useState } from 'react'

const SNAPS = ['peek', 'half', 'full']

function snapOffsets(height) {
  // Сколько пикселей шторки видно в каждом положении (от низа экрана).
  const viewport = window.innerHeight
  return {
    peek: Math.min(262, viewport * 0.36),
    half: viewport * 0.56,
    full: Math.min(height, viewport - 96),
  }
}

/**
 * Панель над картой. На компьютере — колонка слева, на телефоне — шторка снизу
 * с тремя положениями: «чуть видно», «половина» и «на весь экран». Тянется пальцем за ручку.
 */
export default function MapPanel({ mobile, snap, onSnap, header, children }) {
  const ref = useRef(null)
  const drag = useRef(null)
  const [height, setHeight] = useState(() => window.innerHeight)

  useLayoutEffect(() => {
    const update = () => setHeight(window.innerHeight)
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  const offsets = snapOffsets(height)
  const visible = offsets[snap] ?? offsets.half

  useEffect(() => {
    if (ref.current && mobile) ref.current.style.transform = ''
  }, [snap, mobile])

  if (!mobile) {
    return (
      <aside className="map-panel map-panel--side">
        {header}
        <div className="map-panel__body">{children}</div>
      </aside>
    )
  }

  const onPointerDown = (event) => {
    if (event.button !== undefined && event.button !== 0) return
    drag.current = { y: event.clientY, start: visible, time: performance.now(), moved: false }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }

  const onPointerMove = (event) => {
    if (!drag.current || !ref.current) return
    const dy = event.clientY - drag.current.y
    if (Math.abs(dy) > 4) drag.current.moved = true
    const next = Math.max(offsets.peek * 0.6, Math.min(offsets.full, drag.current.start - dy))
    ref.current.style.transform = `translateY(${offsets.full - next}px)`
    ref.current.style.transition = 'none'
  }

  const onPointerUp = (event) => {
    if (!drag.current || !ref.current) return
    const { y, start, time, moved } = drag.current
    drag.current = null
    ref.current.style.transition = ''
    if (!moved) {
      // Нажатие на ручку: переключаем «чуть видно» ↔ «половина».
      onSnap(snap === 'peek' ? 'half' : snap === 'half' ? 'full' : 'half')
      ref.current.style.transform = ''
      return
    }
    const dy = event.clientY - y
    const velocity = dy / Math.max(1, performance.now() - time)
    const position = start - dy
    let target
    if (velocity < -0.5) target = SNAPS[Math.min(2, SNAPS.indexOf(snap) + 1)]
    else if (velocity > 0.5) target = SNAPS[Math.max(0, SNAPS.indexOf(snap) - 1)]
    else target = SNAPS.reduce((best, name) => (Math.abs(offsets[name] - position) < Math.abs(offsets[best] - position) ? name : best), 'half')
    ref.current.style.transform = ''
    onSnap(target)
  }

  return (
    <section
      ref={ref}
      className={`map-panel map-panel--sheet is-${snap}`}
      style={{ height: offsets.full, '--sheet-shift': `${offsets.full - visible}px` }}
    >
      <div
        className="map-panel__handle"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        role="button"
        tabIndex={0}
        aria-label="Развернуть или свернуть панель"
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') onSnap(snap === 'full' ? 'half' : 'full')
        }}
      >
        <span />
      </div>
      {header}
      <div className="map-panel__body">{children}</div>
    </section>
  )
}
