import { useState } from 'react'
import Modal from '../components/Modal'
import { IconDots, IconDownload, IconPlusSquare, IconShare } from '../components/icons'
import { useInstall } from './InstallProvider'

const TABS = [
  ['ios', 'iPhone'],
  ['android', 'Android'],
  ['desktop', 'Компьютер'],
]

/** Шаги установки для каждой платформы и браузера — так, как это выглядит на экране. */
function stepsFor(os, browser) {
  if (os === 'ios') {
    const where = browser === 'safari' || browser === 'other'
      ? 'внизу экрана Safari'
      : 'в адресной строке (iOS 16.4 и новее)'
    return [
      { icon: <IconShare />, title: 'Нажмите «Поделиться»', text: `Квадрат со стрелкой вверх — ${where}.` },
      { icon: <IconPlusSquare />, title: 'Выберите «На экран „Домой“»', text: 'Пролистайте меню вниз, если пункта не видно сразу.' },
      { icon: <b className="guide__chip">Добавить</b>, title: 'Нажмите «Добавить»', text: 'Иконка Рули появится рядом с другими приложениями.' },
    ]
  }
  if (os === 'android') {
    if (browser === 'samsung') {
      return [
        { icon: <b className="guide__chip">≡</b>, title: 'Откройте меню', text: 'Три полоски внизу экрана.' },
        { icon: <IconPlusSquare />, title: '«Добавить страницу на»', text: 'Затем выберите «Главный экран».' },
        { icon: <b className="guide__chip">Добавить</b>, title: 'Подтвердите', text: 'Рули откроется без адресной строки, как обычное приложение.' },
      ]
    }
    if (browser === 'firefox') {
      return [
        { icon: <IconDots />, title: 'Откройте меню ⋮', text: 'Справа от адресной строки.' },
        { icon: <IconDownload />, title: '«Установить»', text: 'Или «Добавить на главный экран».' },
        { icon: <b className="guide__chip">OK</b>, title: 'Подтвердите', text: 'Иконка появится на главном экране.' },
      ]
    }
    return [
      { icon: <IconDots />, title: 'Откройте меню ⋮', text: browser === 'yandex' ? 'Три точки рядом с адресной строкой.' : 'Справа вверху, рядом с адресной строкой.' },
      { icon: <IconDownload />, title: '«Установить приложение»', text: 'В некоторых версиях — «Добавить на главный экран» или «Добавить ярлык».' },
      { icon: <b className="guide__chip">Установить</b>, title: 'Подтвердите', text: 'Через пару секунд Рули появится среди приложений.' },
    ]
  }
  if (browser === 'safari') {
    return [
      { icon: <b className="guide__chip">Файл</b>, title: 'Меню «Файл»', text: 'В верхней строке macOS (Safari 17 и новее).' },
      { icon: <IconPlusSquare />, title: '«Добавить в Dock»', text: 'Рули откроется отдельным окном.' },
    ]
  }
  if (browser === 'firefox') {
    return [
      { icon: <b className="guide__chip">!</b>, title: 'Firefox не устанавливает веб-приложения', text: 'Откройте Рули в Chrome, Edge или Яндекс Браузере — там кнопка установки есть.' },
    ]
  }
  return [
    { icon: <IconDownload />, title: 'Значок в адресной строке', text: 'Справа в строке адреса — монитор со стрелкой. Нажмите его.' },
    { icon: <IconDots />, title: 'Или меню ⋮', text: '«Сохранить и поделиться» → «Установить Рули».' },
    { icon: <b className="guide__chip">Установить</b>, title: 'Подтвердите', text: 'Рули откроется отдельным окном и появится в меню «Пуск».' },
  ]
}

/** Макет телефона с подсвеченной кнопкой — чтобы было понятно, куда нажимать. */
function PhoneHint({ os }) {
  return (
    <div className={`guide-phone guide-phone--${os}`} aria-hidden="true">
      <div className="guide-phone__screen">
        <div className="guide-phone__bar" />
        <span className="guide-phone__logo tag-title">Рули</span>
        <div className="guide-phone__toolbar">
          {os === 'ios' ? (
            <>
              <i />
              <i />
              <span className="guide-phone__target"><IconShare width={16} height={16} /></span>
              <i />
              <i />
            </>
          ) : (
            <span className="guide-phone__target guide-phone__target--top"><IconDots width={16} height={16} /></span>
          )}
        </div>
      </div>
    </div>
  )
}

export default function InstallGuide({ onClose }) {
  const { platform, canPrompt, install, secure, installed } = useInstall()
  const [tab, setTab] = useState(platform.os)
  const steps = stepsFor(tab, tab === platform.os ? platform.browser : tab === 'ios' ? 'safari' : 'chrome')
  const oneTap = canPrompt && tab === platform.os && tab !== 'ios'

  return (
    <Modal title="Рули на главный экран" subtitle="Как настоящее приложение: без адресной строки, с иконкой и быстрым запуском." onClose={onClose}>
      <div className="guide">
        {installed && <div className="notice notice--info">Похоже, Рули уже установлено — ищите иконку на главном экране.</div>}
        {!secure && (
          <div className="notice notice--warn">
            Сейчас сайт открыт без HTTPS — браузер не разрешит установку. Откройте его по защищённому адресу
            (на защите — через туннель, см. README) или на этом компьютере по адресу localhost.
          </div>
        )}

        <div className="segmented" role="tablist">
          {TABS.map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              className={tab === value ? 'is-active' : ''}
              onClick={() => setTab(value)}
            >
              {label}
              {value === platform.os && <small> · у вас</small>}
            </button>
          ))}
        </div>

        {oneTap ? (
          <div className="guide__onetap">
            <p>Ваш браузер умеет ставить Рули в одно нажатие.</p>
            <button
              type="button"
              className="btn btn--cta btn--lg btn--block"
              onClick={async () => {
                const outcome = await install()
                if (outcome === 'accepted') onClose()
              }}
            >
              <IconDownload width={18} height={18} />
              Установить Рули
            </button>
          </div>
        ) : (
          tab !== 'desktop' && <PhoneHint os={tab} />
        )}

        <ol className="guide__steps">
          {steps.map((step, index) => (
            <li key={step.title} style={{ animationDelay: `${index * 90}ms` }}>
              <span className="guide__num">{index + 1}</span>
              <span className="guide__icon">{step.icon}</span>
              <div>
                <b>{step.title}</b>
                <p>{step.text}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="fine-print">
          После установки Рули запускается с главного экрана, открывается быстрее и показывает экран «Нет сети»,
          если пропал интернет. Бронь и оплата всё равно идут только онлайн.
        </p>
      </div>
    </Modal>
  )
}
