import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthProvider } from './context/AuthContext.jsx'
import { FleetProvider } from './context/FleetContext.jsx'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider>
      <FleetProvider>
        <App />
      </FleetProvider>
    </AuthProvider>
  </StrictMode>,
)
