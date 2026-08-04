import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar.jsx'
import Screener from './pages/Screener.jsx'
import StockDetail from './pages/StockDetail.jsx'
import Watchlist from './pages/Watchlist.jsx'
import ModelReport from './pages/ModelReport.jsx'
import TrackRecord from './pages/TrackRecord.jsx'
import Compare from './pages/Compare.jsx'

export default function App() {
  return (
    <div className="app">
      <Navbar />
      <main className="page">
        <Routes>
          <Route path="/" element={<Screener />} />
          <Route path="/stocks/:symbol" element={<StockDetail />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/track-record" element={<TrackRecord />} />
          <Route path="/model" element={<ModelReport />} />
        </Routes>
      </main>
    </div>
  )
}
