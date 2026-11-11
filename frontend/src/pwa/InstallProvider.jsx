import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useTour } from '../tour/TourProvider'
import InstallGuide from './InstallGuide'
import Onboarding from './Onboarding'
import {
  applyUpdate,
  canPrompt,
  detectInstalledApp,
  detectPlatform,
  hasUpdate,
  isStandalone,
  promptInstall,
  subscribe,
  wasInstalled,
} from './pwa'

const ONBOARDED_KEY = 'ruli:onboarded'
const InstallContext = createContext(null)

function readOnboarded() {
  try {
    return localStorage.getItem(ONBOARDED_KEY) === '1'
  } catch {
    return true
  }
}

function snapshot() {
  const standalone = isStandalone()
  return {
    standalone,
    // Уже стоит на телефоне: открыто с главного экрана или браузер сообщил об установке.
    installed: standalone || wasInstalled(),
    canPrompt: canPrompt(),
    updateAvailable: hasUpdate(),
  }
}

export function InstallProvider({ children }) {
  const [state, setState] = useState(snapshot)
  const [guideOpen, setGuideOpen] = useState(false)
  const [onboarding, setOnboarding] = useState(() => !readOnboarded())
  const platform = useMemo(detectPlatform, [])
  const { startIfNew } = useTour()

  useEffect(() => {
    const update = () => setState(snapshot())
    const unsubscribe = subscribe(update)
    detectInstalledApp().then(update)
    return unsubscribe
  }, [])

  const finishOnboarding = useCallback(() => {
    setOnboarding(false)
    // После знакомства — тур по экрану (только в первый раз).
    startIfNew()
    try {
      localStorage.setItem(ONBOARDED_KEY, '1')
    } catch {
      /* в приватном режиме обучалка покажется снова — не страшно */
    }
  }, [startIfNew])

  /** Установить: системное окно браузера, если оно есть, иначе — пошаговая инструкция. */
  const install = useCallback(async () => {
    if (canPrompt()) {
      const outcome = await promptInstall()
      if (outcome !== 'unavailable') return outcome
    }
    setGuideOpen(true)
    return 'guide'
  }, [])

  const value = useMemo(
    () => ({
      ...state,
      platform,
      secure: typeof window !== 'undefined' && window.isSecureContext,
      // Предлагать установку только тем, у кого приложения ещё нет.
      offerInstall: !state.installed,
      install,
      openGuide: () => setGuideOpen(true),
      replayOnboarding: () => setOnboarding(true),
      applyUpdate,
    }),
    [state, platform, install],
  )

  return (
    <InstallContext.Provider value={value}>
      {children}
      {onboarding && <Onboarding onDone={finishOnboarding} />}
      {guideOpen && <InstallGuide onClose={() => setGuideOpen(false)} />}
    </InstallContext.Provider>
  )
}

export function useInstall() {
  const context = useContext(InstallContext)
  if (!context) throw new Error('useInstall используется вне InstallProvider')
  return context
}
