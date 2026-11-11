import { useState } from 'react'
import { IconChevron, IconDownload, IconHelp, IconMap, IconSpark } from '../components/icons'
import { useInstall } from '../pwa/InstallProvider'
import { useTour } from '../tour/TourProvider'

const FAQ = [
  [
    'Как взять машину?',
    'Пройдите Рули ID (телефон, права, лицо — около 5 минут). Выберите машину на карте или в списке «Рядом» и нажмите «Забронировать». Дойдите до машины, сделайте осмотр, подтвердите лицо — машина откроется.',
  ],
  [
    'Сколько бесплатно ждёт бронь?',
    'Столько, сколько вам реально идти до машины: время пешком × 1,3 + 3 минуты, от 10 до 25 минут. «Допуск Плюс» даёт ещё +5. Дальше — ожидание по тарифу.',
  ],
  [
    'Зачем фото при осмотре?',
    'Акт осмотра защищает вас: повреждения, которые уже были, вам не припишут. Каждый акт запечатан хэшем, подменить его задним числом нельзя.',
  ],
  [
    'Почему просят селфи перед поездкой?',
    'Машина открывается только владельцу аккаунта. Так никто не прокатится по вашим правам — и вы не отвечаете за чужую поездку.',
  ],
  [
    'Что такое «Куда едем?»',
    'Укажите адрес — Рули посчитает полную цену поездки на нескольких машинах рядом (пешком, бронь, дорога по лучшему тарифу) и подскажет самую выгодную.',
  ],
  [
    'Как работают баллы «Движа»?',
    '+10 за каждую поездку и +1 за каждые 2 минуты, плюс задания недели и достижения. 100 баллов = 1 BYN, баллами можно оплатить до 30% поездки.',
  ],
  [
    'Сколько стоит поездка?',
    'Поминутно по тарифу класса, но если пакет «Час» или «Сутки» выходит дешевле — он применится сам. Итог видно в чеке.',
  ],
  [
    'Что делать, если машины нет на месте?',
    'Подойдите к точке ближе чем на 300 м и нажмите «Машины нет на месте» — бронь снимется бесплатно, а мы предложим ближайшую замену.',
  ],
]

export default function HelpPage() {
  const { start } = useTour()
  const { replayOnboarding, offerInstall, install } = useInstall()
  const [open, setOpen] = useState(0)

  return (
    <div className="help fade-up">
      <header className="page-head">
        <div className="overline">Обучение</div>
        <h1 className="display">Как рулить</h1>
        <p className="muted">Три способа разобраться: тур по экрану, короткое знакомство и ответы на частые вопросы.</p>
      </header>

      <div className="help-cards">
        <button type="button" className="help-card help-card--acid" onClick={start}>
          <IconMap width={28} height={28} />
          <b>Тур по экрану</b>
          <span>Подсветим кнопки на карте и расскажем, что где</span>
        </button>
        <button type="button" className="help-card help-card--pink" onClick={replayOnboarding}>
          <IconSpark width={28} height={28} />
          <b>Знакомство</b>
          <span>Пять слайдов о том, чем Рули лучше других</span>
        </button>
        {offerInstall && (
          <button type="button" className="help-card" onClick={install}>
            <IconDownload width={28} height={28} />
            <b>Установить</b>
            <span>Рули на главный экран телефона</span>
          </button>
        )}
      </div>

      <section className="card faq">
        <h2>
          <IconHelp width={20} height={20} /> Частые вопросы
        </h2>
        {FAQ.map(([question, answer], index) => (
          <div key={question} className={`faq__item ${open === index ? 'is-open' : ''}`}>
            <button type="button" aria-expanded={open === index} onClick={() => setOpen(open === index ? -1 : index)}>
              {question}
              <IconChevron width={18} height={18} />
            </button>
            <div className={`collapse ${open === index ? 'is-open' : ''}`}>
              <div className="collapse__inner">
                <p>{answer}</p>
              </div>
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}
