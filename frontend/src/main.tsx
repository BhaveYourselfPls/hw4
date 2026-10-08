import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth'
import { MatchesProvider } from './matches'
import { SizeProvider } from './size'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <MatchesProvider>
          <SizeProvider>
            <App />
          </SizeProvider>
        </MatchesProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
