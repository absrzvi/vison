import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { FleetProvider } from './context/FleetContext.jsx'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <FleetProvider>
      <App />
    </FleetProvider>
  </StrictMode>,
)
