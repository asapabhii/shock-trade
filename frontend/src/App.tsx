import { BrowserRouter, Routes, Route } from 'react-router-dom'

import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AllSports from './pages/AllSports'
import Trades from './pages/Trades'
import Positions from './pages/Positions'
import Settings from './pages/Settings'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="sports" element={<AllSports />} />
          <Route path="trades" element={<Trades />} />
          <Route path="positions" element={<Positions />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
