import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const KEY = 'ruli:theme'
const MODES = ['auto', 'night', 'day']
export const MODE_LABELS = { auto: 'Как в системе', night: 'Ночь', day: 'День' }
// Цвет строки состояния телефона и заголовка окна установленного приложения.
const BAR_COLORS = { night: '#1834D6', day: '#E7E4DC' }

const ThemeContext = createContext(null)

function systemTheme() {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'day' : 'night'
}

function readMode() {
  try {
    const saved = localStorage.getItem(KEY)
    return MODES.includes(saved) ? saved : 'auto'
  } catch {
    return 'auto'
  }
}

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(readMode)
  const [system, setSystem] = useState(systemTheme)
  const theme = mode === 'auto' ? system : mode

  useEffect(() => {
    const query = window.matchMedia?.('(prefers-color-scheme: light)')
    if (!query) return undefined
    const onChange = () => setSystem(systemTheme())
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', BAR_COLORS[theme])
  }, [theme])

  const setMode = useCallback((next) => {
    setModeState(next)
    try {
      localStorage.setItem(KEY, next)
    } catch {
      /* приватный режим — тема просто не запомнится */
    }
  }, [])

  const cycle = useCallback(() => setMode(MODES[(MODES.indexOf(mode) + 1) % MODES.length]), [mode, setMode])

  const value = useMemo(() => ({ mode, theme, setMode, cycle }), [mode, theme, setMode, cycle])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme используется вне ThemeProvider')
  return context
}
