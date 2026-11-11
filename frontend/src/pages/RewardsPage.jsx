import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  IconBolt,
  IconCar,
  IconCheck,
  IconLock,
  IconMoon,
  IconMore,
  IconRoute,
  IconSeal,
  IconSearch,
  IconShare,
  IconShield,
  IconSpark,
  IconSun,
  IconUser,
} from '../components/icons'
import { useLeaderboard, useRewards, useRewardsHistory } from '../hooks/useRewards'
import { Ticker } from '../components/Splash'
import { useUi } from '../ui/UiProvider'
import { plural } from '../utils/plural'

const ICONS = {
  shield: IconShield,
  spark: IconSpark,
  car: IconCar,
  bolt: IconBolt,
  moon: IconMoon,
  sun: IconSun,
  route: IconRoute,
  seal: IconSeal,
  grid: IconMore,
  search: IconSearch,
  user: IconUser,
}
const PERIODS = [
  ['week', '7 дней'],
  ['month', 'Месяц'],
  ['all', 'Всё время'],
]
const POINTS = ['балл', 'балла', 'баллов']
const TABS = [
  ['quests', 'Задания'],
  ['achievements', 'Награды'],
  ['leaders', 'Рейтинг'],
  ['friends', 'Друзья'],
]

const formatDate = (value) =>
  new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

function daysLeft(value) {
  const days = Math.max(0, Math.ceil((new Date(value) - Date.now()) / 86_400_000))
  return plural(days, ['день', 'дня', 'дней'])
}

function Hero({ data }) {
  const next = data.next_rank
  const progress = next ? (data.earned - data.rank.from) / (next.from - data.rank.from) : 1
  return (
    <section className="rewards-hero">
      <div className="rewards-hero__balance">
        <span className="overline">Баланс</span>
        <b className="num">{data.balance}</b>
        <small>{plural(data.balance, POINTS).replace(/^\d+ /, '')} ≈ {data.balance_byn.replace('.', ',')} BYN</small>
      </div>
      <div className="rewards-hero__rank">
        <span className="sticker sticker--pink">Ранг</span>
        <h2 className="tag-title">{data.rank.title}</h2>
        <p>{data.rank.text}</p>
        <div className="rank-bar" aria-label={`Прогресс до ранга ${next?.title || ''}`}>
          <span style={{ width: `${Math.min(100, progress * 100)}%` }} />
        </div>
        <small>
          {next
            ? `Ещё ${plural(next.from - data.earned, POINTS)} до «${next.title}»`
            : 'Максимальный ранг — ты легенда улиц'}
        </small>
      </div>
      <div className="rewards-hero__rules">
        <div>
          <b>+{data.rules.trip_base}</b>за поездку
        </div>
        <div>
          <b>+1</b>за каждые {data.rules.per_minutes} мин
        </div>
        <div>
          <b>1 BYN</b>за 100 баллов, до {Number(data.rules.max_discount_share) * 100}% поездки
        </div>
      </div>
    </section>
  )
}

function Quests({ data }) {
  return (
    <section className="rewards-block">
      <header className="rewards-block__head">
        <h2>Задания недели</h2>
        <span className="muted">Обновятся через {daysLeft(data.week_ends)}</span>
      </header>
      <div className="quests">
        {data.quests.map((quest, index) => (
          <article
            key={quest.code}
            className={`quest ${quest.done ? 'is-done' : ''}`}
            style={{ animationDelay: `${index * 70}ms` }}
          >
            <div className="quest__top">
              <b>{quest.title}</b>
              <span className="quest__reward">+{quest.points}</span>
            </div>
            <div className="quest__bar">
              <span style={{ width: `${(quest.progress / quest.target) * 100}%` }} />
            </div>
            <small>
              {quest.done ? (
                <>
                  <IconCheck width={12} height={12} strokeWidth={3} /> Выполнено, баллы начислены
                </>
              ) : (
                `${quest.progress} из ${quest.target} ${quest.unit}`
              )}
            </small>
          </article>
        ))}
      </div>
    </section>
  )
}

function Achievements({ data }) {
  const unlocked = data.achievements.filter((item) => item.unlocked).length
  return (
    <section className="rewards-block">
      <header className="rewards-block__head">
        <h2>Достижения</h2>
        <span className="muted">
          Открыто {unlocked} из {data.achievements.length}
        </span>
      </header>
      <div className="badges">
        {data.achievements.map((item, index) => {
          const Icon = ICONS[item.icon] || IconSpark
          return (
            <article
              key={item.code}
              className={`badge-card ${item.unlocked ? 'is-unlocked' : ''}`}
              style={{ '--tilt': `${(index % 3) - 1}deg`, animationDelay: `${index * 50}ms` }}
            >
              <span className="badge-card__icon">
                {item.unlocked ? <Icon width={26} height={26} /> : <IconLock width={22} height={22} />}
              </span>
              <b>{item.title}</b>
              <small>{item.text}</small>
              {item.points > 0 && <span className="badge-card__points">+{item.points}</span>}
            </article>
          )
        })}
      </div>
    </section>
  )
}

function Leaderboard() {
  const [period, setPeriod] = useState('week')
  const { data, isLoading } = useLeaderboard(period)
  const podium = data?.top.slice(0, 3) || []
  const rest = data?.top.slice(3) || []

  return (
    <section className="rewards-block">
      <header className="rewards-block__head">
        <h2>Рейтинг райдеров</h2>
        <div className="segmented">
          {PERIODS.map(([value, label]) => (
            <button key={value} type="button" className={period === value ? 'is-active' : ''} onClick={() => setPeriod(value)}>
              {label}
            </button>
          ))}
        </div>
      </header>

      {isLoading && <div className="skeleton" style={{ height: 260 }} />}
      {data && data.top.length === 0 && <div className="state">В этом периоде ещё никто не набрал баллов. Будь первым!</div>}

      {podium.length > 0 && (
        <div className="podium">
          {[podium[1], podium[0], podium[2]].filter(Boolean).map((row) => (
            <div key={row.place} className={`podium__place podium__place--${row.place} ${row.me ? 'is-me' : ''}`}>
              <span className="podium__avatar">{row.initials}</span>
              <b>{row.name}</b>
              <small>{row.rank}</small>
              <div className="podium__step">
                <span className="tag-title">{row.place}</span>
                <em className="num">{row.score}</em>
              </div>
            </div>
          ))}
        </div>
      )}

      {rest.length > 0 && (
        <ol className="leaders">
          {rest.map((row) => (
            <li key={row.place} className={row.me ? 'is-me' : ''}>
              <span className="leaders__place num">{row.place}</span>
              <span className="leaders__avatar">{row.initials}</span>
              <span className="leaders__name">
                <b>{row.name}</b>
                <small>
                  {row.rank} · {plural(row.trips, ['поездка', 'поездки', 'поездок'])}
                </small>
              </span>
              <b className="leaders__score num">{row.score}</b>
            </li>
          ))}
        </ol>
      )}

      {data?.me && !data.top.some((row) => row.me) && (
        <ol className="leaders leaders--me">
          <li className="is-me">
            <span className="leaders__place num">{data.me.place}</span>
            <span className="leaders__avatar">{data.me.initials}</span>
            <span className="leaders__name">
              <b>Это ты</b>
              <small>{data.me.rank}</small>
            </span>
            <b className="leaders__score num">{data.me.score}</b>
          </li>
        </ol>
      )}
      <p className="fine-print">В рейтинге — имя и первая буква фамилии. Считаются заработанные баллы, траты место не снижают.</p>
    </section>
  )
}

function Friends({ data }) {
  const { notify } = useUi()
  const { referral } = data
  const link = `${window.location.origin}/register?ref=${referral.code}`

  const share = async () => {
    const text = `Катаюсь на Рули — каршеринг в Минске. Регистрируйся по моему коду ${referral.code}, и мы оба получим по ${referral.points} баллов!`
    if (navigator.share) {
      try {
        await navigator.share({ title: 'Рули', text, url: link })
        return
      } catch {
        /* пользователь закрыл окно — скопируем ссылку */
      }
    }
    try {
      await navigator.clipboard.writeText(`${text} ${link}`)
      notify('Ссылка скопирована', { description: 'Отправьте её другу в мессенджере.' })
    } catch {
      notify('Ваш код', { description: referral.code, tone: 'info' })
    }
  }

  return (
    <section className="rewards-block">
      <header className="rewards-block__head">
        <h2>Приведи друга</h2>
      </header>
      <div className="invite">
        <div>
          <p>
            Друг регистрируется по твоему коду и завершает первую поездку — вам обоим по{' '}
            <b>{referral.points} баллов</b>.
          </p>
          <div className="invite__code num">{referral.code}</div>
          <small className="muted">
            Пришли: {referral.friends} · прокатились: {referral.rewarded}
          </small>
        </div>
        <button type="button" className="btn btn--cta btn--lg" onClick={share}>
          <IconShare width={18} height={18} />
          Поделиться
        </button>
      </div>
    </section>
  )
}

function History() {
  const { data = [] } = useRewardsHistory()
  if (!data.length) return null
  return (
    <section className="rewards-block">
      <header className="rewards-block__head">
        <h2>История баллов</h2>
      </header>
      <ul className="points-history">
        {data.slice(0, 15).map((entry) => (
          <li key={entry.id}>
            <span>
              <b>{entry.title}</b>
              <small>{formatDate(entry.created_at)}</small>
            </span>
            <em className={`num ${entry.amount < 0 ? 'is-minus' : ''}`}>
              {entry.amount > 0 ? '+' : ''}
              {entry.amount}
            </em>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function RewardsPage() {
  const { isAuthenticated } = useAuth()
  const { data, isLoading } = useRewards()
  const [tab, setTab] = useState('quests')

  return (
    <div className="rewards fade-up">
      <header className="page-head">
        <div className="overline">Баллы · задания · рейтинг</div>
        <h1 className="display">Движ</h1>
        <p className="muted">Катайся, выполняй задания, собирай теги и забирай скидку баллами.</p>
      </header>

      <Ticker words={['Катайся', 'Собирай теги', 'Забирай скидку', 'Будь королём улиц']} />

      {!isAuthenticated ? (
        <>
          <div className="card rewards-guest">
            <h2>Войди, чтобы копить баллы</h2>
            <p className="muted">Рейтинг виден всем — а свои баллы и задания появятся после входа.</p>
            <Link to="/login" className="btn btn--cta">
              Войти
            </Link>
          </div>
          <Leaderboard />
        </>
      ) : isLoading || !data ? (
        <div className="skeleton" style={{ height: 320 }} />
      ) : (
        <>
          <Hero data={data} />
          <div className="segmented rewards-tabs" role="tablist">
            {TABS.map(([value, label]) => (
              <button key={value} type="button" role="tab" aria-selected={tab === value} className={tab === value ? 'is-active' : ''} onClick={() => setTab(value)}>
                {label}
              </button>
            ))}
          </div>
          <div key={tab} className="rewards-tab fade-up">
            {tab === 'quests' && (
              <>
                <Quests data={data} />
                <History />
              </>
            )}
            {tab === 'achievements' && <Achievements data={data} />}
            {tab === 'leaders' && <Leaderboard />}
            {tab === 'friends' && <Friends data={data} />}
          </div>
        </>
      )}
    </div>
  )
}
