import { useMemo } from 'react'

const COLORS = ['var(--acid)', 'var(--pink)', 'var(--cobalt-2)', '#ffffff']

/** Салют из клякс краски — для чека с наградами и открытых достижений. */
export default function Splash({ count = 22 }) {
  const drops = useMemo(
    () =>
      Array.from({ length: count }, (_, index) => {
        const angle = (index / count) * Math.PI * 2 + Math.random() * 0.4
        const distance = 70 + Math.random() * 110
        return {
          x: Math.cos(angle) * distance,
          y: Math.sin(angle) * distance,
          size: 6 + Math.random() * 14,
          color: COLORS[index % COLORS.length],
          delay: Math.random() * 120,
        }
      }),
    [count],
  )
  return (
    <span className="splash" aria-hidden="true">
      {drops.map((drop, index) => (
        <i
          key={index}
          style={{
            '--x': `${drop.x}px`,
            '--y': `${drop.y}px`,
            width: drop.size,
            height: drop.size,
            background: drop.color,
            animationDelay: `${drop.delay}ms`,
          }}
        />
      ))}
    </span>
  )
}

/** Бегущая строка, как лента на заборе. */
export function Ticker({ words }) {
  const line = [...words, ...words, ...words]
  return (
    <div className="ticker" aria-hidden="true">
      <div className="ticker__track">
        {[0, 1].map((copy) => (
          <span key={copy}>
            {line.map((word, index) => (
              <b key={`${copy}-${index}`}>
                {word}
                <i>✦</i>
              </b>
            ))}
          </span>
        ))}
      </div>
    </div>
  )
}
