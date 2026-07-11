import { useCallback, useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchStock } from '../api.js'
import PriceChart from '../components/PriceChart.jsx'
import StatsGrid from '../components/StatsGrid.jsx'
import IndicatorPanel from '../components/IndicatorPanel.jsx'
import PredictionCard from '../components/PredictionCard.jsx'
import AddToWatchlistModal from '../components/AddToWatchlistModal.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import { fmtMoney, fmtPct, changeClass } from '../utils/format.js'

export default function StockDetail() {
  const { symbol } = useParams()
  // result is stale when it belongs to a different symbol (route change)
  const [result, setResult] = useState(null)
  const [showModal, setShowModal] = useState(false)

  const load = useCallback(() => {
    fetchStock(symbol)
      .then((data) => setResult({ symbol, data }))
      .catch((error) => setResult({ symbol, error }))
  }, [symbol])

  useEffect(() => {
    load()
  }, [load])

  const stale = !result || result.symbol !== symbol
  const data = stale ? null : result.data
  const error = stale ? null : result.error

  if (error) {
    return (
      <div>
        <ErrorBanner error={error} />
        <Link to="/">← Back to screener</Link>
      </div>
    )
  }
  if (!data) return <LoadingSpinner label={`Loading ${symbol}…`} />

  const s = data.snapshot

  return (
    <div>
      <div className="detail-header">
        <h1>{s.symbol}</h1>
        <span style={{ color: 'var(--text-dim)' }}>{s.name}</span>
        <span className="price">{fmtMoney(s.price)}</span>
        <span className={changeClass(s.change_1d)} style={{ fontSize: 18 }}>
          {fmtPct(s.change_1d)} today
        </span>
        <span style={{ flex: 1 }} />
        <button onClick={() => setShowModal(true)} disabled={data.in_watchlist}>
          {data.in_watchlist ? 'In watchlist ✓' : '+ Add to watchlist'}
        </button>
      </div>
      <p className="subtitle">
        {s.sector || 'Unknown sector'}{data.industry ? ` · ${data.industry}` : ''} · data as of {s.as_of_date}
      </p>
      <StatsGrid snapshot={s} />
      <div className="detail-grid">
        <PriceChart symbol={s.symbol} />
        <div>
          <PredictionCard symbol={s.symbol} />
          <IndicatorPanel symbol={s.symbol} />
        </div>
      </div>
      {showModal && (
        <AddToWatchlistModal
          symbol={s.symbol}
          onClose={() => setShowModal(false)}
          onSaved={load}
        />
      )}
    </div>
  )
}
