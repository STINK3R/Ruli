import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'

const DONE_KEY = 'ruli:tour-done'
const TourContext = createContext(null)

/** Шаги тура по главному экрану. Для каждого — список селекторов: первый видимый и подсвечивается. */
const STEPS = [
  {
    targets: ['.planner-bar'],
    title: 'Куда едем?',
    text: 'Введите адрес или ткните в карту — Рули сравнит машины рядом по полной цене поездки и покажет самую выгодную.',
  },
  {
    targets: ['.car-list .car-row'],
    title: 'Машины рядом',
    text: 'Жёлтая плашка — сколько идти пешком. Список начинается с ближайшей. Нажмите — откроется карточка с ценой и бронью.',
  },
  {
    targets: ['.chips'],
    title: 'Фильтры',
    text: 'Класс машины и «только свободные». Подробные фильтры — кнопкой «Фильтры» над списком.',
  },
  {
    targets: ['.map-controls'],
    title: 'Где я',
    text: 'Стрелка найдёт вас на карте. Правый клик или долгое нажатие по карте — отметить, где вы стоите.',
  },
  {
    targets: ['.tabbar a[href="/rewards"]', '.topbar__nav a[href="/rewards"]'],
    title: 'Движ',
    text: 'Баллы за поездки, задания недели, достижения и рейтинг райдеров. 100 баллов = 1 BYN скидки.',
  },
  {
    targets: ['.tabbar a[href="/verification"]', '.topbar__nav a[href="/verification"]'],
    title: 'Рули ID',
    text: 'Перед первой бронью подтвердите телефон, права и лицо — около 5 минут.',
  },
  {
    targets: ['.tabbar__item:last-child', '.topbar__user', '.topbar__install'],
    title: 'Меню',
    text: 'Тема «Ночь/День», установка приложения на телефон и это обучение — всегда здесь.',
  },
]

function visible(element) {
  const rect = element.getBoundingClientRect()
  return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight
}

function findTarget(step) {
  for (const selector of step.targets) {
    const element = [...document.querySelectorAll(selector)].find(visible)
    if (element) return element
  }
  return null
}

function Tour({ onClose }) {
  const [index, setIndex] = useState(0)
  const [rect, setRect] = useState(null)
  const steps = STEPS
  const step = steps[index]

  // Шаг без цели на этом экране (например, нет машин) пропускаем.
  useLayoutEffect(() => {
    let frame = 0
    let tries = 0
    const measure = () => {
      const element = findTarget(step)
      if (!element) {
        tries += 1
        if (tries < 20) frame = requestAnimationFrame(measure)
        else if (index < steps.length - 1) setIndex(index + 1)
        else onClose()
        return
      }
      const box = element.getBoundingClientRect()
      setRect({ top: box.top, left: box.left, width: box.width, height: box.height })
    }
    measure()
    const update = () => measure()
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [index])

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowRight') setIndex((value) => Math.min(value + 1, steps.length - 1))
      if (event.key === 'ArrowLeft') setIndex((value) => Math.max(value - 1, 0))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (!rect) return null
  const pad = 8
  const below = rect.top + rect.height / 2 < window.innerHeight / 2
  const width = Math.min(340, window.innerWidth - 24)
  const left = Math.min(Math.max(12, rect.left + rect.width / 2 - width / 2), window.innerWidth - width - 12)
  const bubble = below
    ? { top: rect.top + rect.height + pad + 14, left, width }
    : { bottom: window.innerHeight - rect.top + pad + 14, left, width }
  const last = index === steps.length - 1

  return createPortal(
    <div className="tour" role="dialog" aria-modal="true" aria-label="Обучение">
      <div
        className="tour__spot"
        style={{ top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }}
      />
      <div className={`tour__bubble ${below ? 'is-below' : 'is-above'}`} style={bubble} key={index}>
        <span className="tour__count">
          {index + 1} / {steps.length}
        </span>
        <h3>{step.title}</h3>
        <p>{step.text}</p>
        <div className="tour__actions">
          <button type="button" className="link-gold" onClick={onClose}>
            Пропустить
          </button>
          <div>
            {index > 0 && (
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setIndex(index - 1)}>
                Назад
              </button>
            )}
            <button type="button" className="btn btn--cta btn--sm" onClick={() => (last ? onClose() : setIndex(index + 1))}>
              {last ? 'Готово' : 'Дальше'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

export function TourProvider({ children }) {
  const [active, setActive] = useState(false)
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const start = useCallback(() => {
    if (pathname !== '/') navigate('/')
    // Даём карте и списку отрисоваться.
    setTimeout(() => setActive(true), pathname === '/' ? 150 : 900)
  }, [pathname, navigate])

  const close = useCallback(() => {
    setActive(false)
    try {
      localStorage.setItem(DONE_KEY, '1')
    } catch {
      /* не запомним — не страшно */
    }
  }, [])

  const value = useMemo(
    () => ({
      start,
      // Сам тур запускается только на карте: со ссылки друга или страницы входа не уводим.
      startIfNew: () => {
        if (pathname !== '/') return
        try {
          if (localStorage.getItem(DONE_KEY) === '1') return
        } catch {
          return
        }
        start()
      },
    }),
    [start, pathname],
  )

  return (
    <TourContext.Provider value={value}>
      {children}
      {active && <Tour onClose={close} />}
    </TourContext.Provider>
  )
}

export function useTour() {
  const context = useContext(TourContext)
  if (!context) throw new Error('useTour используется вне TourProvider')
  return context
}
