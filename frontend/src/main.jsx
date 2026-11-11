import './pwa/pwa' // первым: ловит предложение установки до монтирования React
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@fontsource/rubik-wet-paint/cyrillic-400.css'
import '@fontsource/rubik-wet-paint/latin-400.css'
import '@fontsource/rubik-spray-paint/cyrillic-400.css'
import '@fontsource/rubik-spray-paint/latin-400.css'
import '@fontsource-variable/unbounded'
import '@fontsource-variable/onest'
import 'maplibre-gl/dist/maplibre-gl.css'
import './styles/tokens.css'
import './styles/base.css'
import './styles/shell.css'
import './styles/map.css'
import './styles/pages.css'
import './styles/kyc.css'
import './styles/rewards.css'
import './styles/tour.css'
import App from './App'
import { AuthProvider } from './auth/AuthContext'
import { LocationProvider } from './location/LocationContext'
import { InstallProvider } from './pwa/InstallProvider'
import { registerServiceWorker } from './pwa/pwa'
import { ThemeProvider } from './theme/ThemeProvider'
import { TourProvider } from './tour/TourProvider'
import { UiProvider } from './ui/UiProvider'

registerServiceWorker()

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <LocationProvider>
              <UiProvider>
                <TourProvider>
                  <InstallProvider>
                    <App />
                  </InstallProvider>
                </TourProvider>
              </UiProvider>
            </LocationProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
