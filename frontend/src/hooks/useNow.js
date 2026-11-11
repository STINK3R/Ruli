import { useEffect, useState } from 'react'

/** Текущее время, обновляемое раз в секунду, пока компонент активен. */
export function useNow(enabled = true) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!enabled) return undefined
    setNow(Date.now())
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [enabled])

  return now
}
