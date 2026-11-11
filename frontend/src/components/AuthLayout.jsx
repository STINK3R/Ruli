const PERKS = [
  ['Честная бронь', 'ждём столько, сколько идти до машины'],
  ['Куда едем?', 'подскажем, какая машина выйдет дешевле'],
  ['Паспорт кузова', 'чужие царапины вам не припишут'],
  ['Рули ID', 'за рулём только проверенные водители'],
]

export default function AuthLayout({ title, subtitle, wide = false, children }) {
  return (
    <div className="auth-split fade-up">
      <aside className="auth-hero">
        <span className="sticker sticker--outline auth-hero__sticker">Минск · 24/7</span>
        <div className="auth-hero__tag tag-title" aria-hidden="true">
          Рули
        </div>
        <h2 className="auth-hero__title">
          Каршеринг от <em>0,29 BYN</em> в минуту
        </h2>
        <ul className="auth-hero__perks">
          {PERKS.map(([perk, text], index) => (
            <li key={perk} style={{ animationDelay: `${120 + index * 80}ms` }}>
              <b>{perk}</b>
              <span>{text}</span>
            </li>
          ))}
        </ul>
        <img className="auth-hero__car" src="/cars/toyota-camry.webp" alt="" aria-hidden="true" />
      </aside>

      <div className={`auth-form ${wide ? 'auth-form--wide' : ''}`}>
        <h1 className="display drip">{title}</h1>
        <p className="muted">{subtitle}</p>
        {children}
      </div>
    </div>
  )
}
