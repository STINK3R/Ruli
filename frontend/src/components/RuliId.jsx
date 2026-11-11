import { Link } from 'react-router-dom'
import { plural } from '../utils/plural'
import { IconCheck, IconLock } from './icons'

const LEVELS = [
  ['Гость', 'Смотрит карту и цены'],
  ['На проверке', 'Документы у модератора'],
  ['Проверенный водитель', 'Бронь по маршруту, классы — по возрасту и стажу'],
  ['Допуск Плюс', '+5 минут бесплатной брони и классы, где нужны поездки'],
]

const REASON_LABELS = {
  verification: 'нужна проверка прав',
  phone: 'нужно подтвердить телефон',
  age: 'возраст',
  experience: 'стаж',
  trips: 'поездки без замечаний',
}

const YEARS = ['года', 'лет', 'лет']
const CLEAN_TRIPS = ['чистая поездка', 'чистые поездки', 'чистых поездок']

/** «от 21 года», «от 18 лет»: после «от» — родительный падеж. */
const ageLabel = (age) => plural(age, YEARS)

const formatDate = (value) =>
  value ? new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }) : ''

/** Лестница уровней «Рули ID»: доверие растёт вместе с чистыми поездками. */
export function LevelLadder({ access }) {
  return (
    <ol className="ladder">
      {LEVELS.map(([title, text], level) => (
        <li
          key={title}
          className={`ladder__step ${level < access.level ? 'is-done' : ''} ${
            level === access.level ? 'is-current' : ''
          }`}
        >
          <span className="ladder__mark">
            {level < access.level ? <IconCheck width={12} height={12} strokeWidth={3} /> : level}
          </span>
          <div>
            <div className="ladder__title">{title}</div>
            <div className="ladder__text">{text}</div>
          </div>
        </li>
      ))}
    </ol>
  )
}

export function TripsProgress({ access }) {
  if (access.level < 2) return null
  const done = Math.min(access.clean_trips, access.plus_target)
  return (
    <div className="trips-progress">
      <div className="trips-progress__head">
        <span>Поездки без замечаний за 180 дней</span>
        <b>
          {access.clean_trips} / {access.plus_target}
        </b>
      </div>
      <div className="trips-progress__bar">
        {Array.from({ length: access.plus_target }).map((_, index) => (
          <span key={index} className={index < done ? 'is-on' : ''} />
        ))}
      </div>
    </div>
  )
}

export function ClassAccess({ access }) {
  return (
    <div className="class-access">
      {Object.entries(access.classes).map(([key, entry]) => (
        <div key={key} className={`class-access__row ${entry.allowed ? 'is-open' : ''}`}>
          <span className="class-access__icon">
            {entry.allowed ? (
              <IconCheck width={14} height={14} strokeWidth={2.8} />
            ) : (
              <IconLock width={14} height={14} />
            )}
          </span>
          <div className="class-access__main">
            <div className="class-access__label">{entry.label}</div>
            {entry.requirement && (
              <div className="class-access__req">
                от {ageLabel(entry.requirement.min_age)}
                {entry.requirement.min_experience_years
                  ? ` · стаж от ${plural(entry.requirement.min_experience_years, YEARS)}`
                  : ''}
                {entry.requirement.min_completed_rentals
                  ? ` · ${plural(entry.requirement.min_completed_rentals, CLEAN_TRIPS)}`
                  : ''}
              </div>
            )}
          </div>
          <div className="class-access__state">
            {entry.allowed
              ? 'Открыт'
              : entry.unlock_on
                ? `с ${formatDate(entry.unlock_on)}`
                : entry.reasons.map((reason) => REASON_LABELS[reason]).join(', ')}
          </div>
        </div>
      ))}
    </div>
  )
}

/** Компактная карточка «Рули ID» для профиля. */
export default function RuliIdCard({ access }) {
  if (!access) return null
  const approved = access.level >= 2
  return (
    <section className="card ruli-id">
      <div className="ruli-id__head">
        <div>
          <div className="overline overline--gold">Рули ID</div>
          <h2 className="display">{access.level_display}</h2>
          <p className="muted">{access.next_step}</p>
        </div>
        <span className={`ruli-id__seal level-${access.level}`}>
          <span>Р</span>
        </span>
      </div>

      {access.license_expires_soon && (
        <div className="notice notice--warn">
          Права истекают {formatDate(access.license_expires_on)} — загрузите новое удостоверение
          заранее, чтобы не потерять доступ.
        </div>
      )}
      {access.novice && (
        <div className="notice">
          Стаж меньше двух лет: бизнес и премиум откроются позже — даты указаны ниже.
        </div>
      )}

      <LevelLadder access={access} />
      <TripsProgress access={access} />
      <ClassAccess access={access} />

      <Link to="/verification" className={`btn btn--block ${approved ? 'btn--soft' : 'btn--cta'}`}>
        {approved ? 'Документы и согласия' : access.level === 1 ? 'Статус проверки' : 'Подтвердить права'}
      </Link>
    </section>
  )
}
