import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconChevron, IconDownload, IconFace, IconRoute, IconSeal, IconWalk } from '../components/icons'
import { useInstall } from './InstallProvider'

const SLIDES = [
  {
    key: 'hello',
    tag: 'Каршеринг Минска',
    title: 'Рули',
    text: 'Машина в паре минут пешком. Без скрытых минут, без чужих царапин, без фейковых водителей.',
    image: '/cars/volkswagen-tiguan.webp',
  },
  {
    key: 'fair',
    tag: 'Честная бронь',
    title: 'Ждём столько, сколько идти',
    text: 'Бесплатное ожидание считается по реальному пешему маршруту до машины, а не «10 минут для всех».',
    icon: <IconWalk />,
  },
  {
    key: 'plan',
    tag: 'Куда едем?',
    title: 'Ближайшая ≠ выгодная',
    text: 'Скажите адрес — Рули сравнит машины рядом по полной цене поездки и покажет самую выгодную.',
    icon: <IconRoute />,
  },
  {
    key: 'passport',
    tag: 'Паспорт кузова',
    title: 'Чужие царапины — не ваши',
    text: 'Акты осмотра с фото запечатаны цепочкой хэшей: задним числом их не подменить.',
    icon: <IconSeal />,
  },
  {
    key: 'id',
    tag: 'Рули ID',
    title: 'За рулём — только проверенные',
    text: 'Права сверяются с реестром ГАИ, лицо — проверкой «живости». Перед поездкой — короткое селфи.',
    icon: <IconFace />,
  },
]

export default function Onboarding({ onDone }) {
  const { offerInstall, install, platform } = useInstall()
  const slides = offerInstall ? [...SLIDES, { key: 'install' }] : SLIDES
  const [index, setIndex] = useState(0)
  const touch = useRef(null)
  const last = index === slides.length - 1
  const slide = slides[index]

  const next = () => (last ? onDone() : setIndex((value) => Math.min(value + 1, slides.length - 1)))
  const prev = () => setIndex((value) => Math.max(0, value - 1))

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'ArrowRight') next()
      if (event.key === 'ArrowLeft') prev()
      if (event.key === 'Escape') onDone()
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  })

  return createPortal(
    <div
      className="onboarding"
      role="dialog"
      aria-modal="true"
      aria-label="Знакомство с Рули"
      onTouchStart={(event) => (touch.current = event.touches[0].clientX)}
      onTouchEnd={(event) => {
        if (touch.current == null) return
        const dx = event.changedTouches[0].clientX - touch.current
        if (dx < -50) next()
        if (dx > 50) prev()
        touch.current = null
      }}
    >
      <button type="button" className="onboarding__skip" onClick={onDone}>
        Пропустить
      </button>

      <div key={slide.key} className={`onboarding__slide onboarding__slide--${slide.key}`}>
        {slide.key === 'install' ? (
          <>
            <div className="onboarding__art onboarding__art--app">
              <img src="/icons/icon-512.png" alt="" />
            </div>
            <span className="sticker sticker--pink">Одно нажатие</span>
            <h2 className="display drip">Поставь на телефон</h2>
            <p>
              Рули откроется с главного экрана как обычное приложение — без адресной строки и быстрее.
              {platform.os === 'ios' && ' На iPhone — через «Поделиться» → «На экран „Домой“».'}
            </p>
            <div className="onboarding__actions">
              <button
                type="button"
                className="btn btn--cta btn--lg"
                onClick={async () => {
                  const outcome = await install()
                  if (outcome === 'accepted') onDone()
                }}
              >
                <IconDownload width={18} height={18} />
                {platform.os === 'ios' ? 'Показать как' : 'Установить'}
              </button>
              <button type="button" className="btn btn--ghost btn--lg" onClick={onDone}>
                Позже
              </button>
            </div>
            <p className="fine-print">Кнопка установки всегда есть в меню «Ещё».</p>
          </>
        ) : (
          <>
            <div className="onboarding__art">
              {slide.image ? <img className="onboarding__car" src={slide.image} alt="" /> : <span className="onboarding__icon">{slide.icon}</span>}
            </div>
            <span className="sticker">{slide.tag}</span>
            <h2 className={`display ${index === 0 ? 'onboarding__logo' : ''} drip`}>{slide.title}</h2>
            <p>{slide.text}</p>
          </>
        )}
      </div>

      <div className="onboarding__footer">
        <div className="onboarding__dots">
          {slides.map((item, i) => (
            <button
              key={item.key}
              type="button"
              className={i === index ? 'is-active' : ''}
              aria-label={`Слайд ${i + 1}`}
              onClick={() => setIndex(i)}
            />
          ))}
        </div>
        {slide.key !== 'install' && (
          <button type="button" className="btn btn--cta btn--lg" onClick={next}>
            {last ? 'Погнали' : 'Дальше'}
            <IconChevron width={18} height={18} />
          </button>
        )}
      </div>
    </div>,
    document.body,
  )
}
