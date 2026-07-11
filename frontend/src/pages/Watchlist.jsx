import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchWatchlist, deleteWatchlistItem } from '../api.js'
import AddToWatchlistModal from '../components/AddToWatchlistModal.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { fmtMoney, fmtPct, fmtNumber, changeClass } from '../utils/format.js'

export default function Watchlist() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(null)

  const load = useCallback(() => {
    fetchWatchlist().then(setData).catch(setError)
  }, [])

  useEffect(() => {
    load()
    window.addEventListener('data-refreshed', load)
    return () => window.removeEventListener('data-refreshed', load)
  }, [load])

  const remove = async (item) => {
    if (!window.confirm(`Remove ${item.symbol} from watchlist?`)) return
    await deleteWatchlistItem(item.id)
    load()
  }

  if (error) return <ErrorBanner error={error} />
  if (!data) return <LoadingSpinner label="Loading watchlist…" />

  return (
    <div>
      <h1>Watchlist</h1>
      <p className="subtitle">Track positions and ideas with live valuation and AI scores.</p>

      {data.total_value != null && (
        <div className="totals-row panel">
          <div className="item">
            <div className="label">Portfolio value</div>
            <div className="value">{fmtMoney(data.total_value)}</div>
          </div>
          <div className="item">
            <div className="label">Cost basis</div>
            <div className="value">{fmtMoney(data.total_cost)}</div>
          </div>
          <div className="item">
            <div className="label">Gain / loss</div>
            <div className={`value ${changeClass(data.total_gain_loss)}`}>
              {fmtMoney(data.total_gain_loss)} ({fmtPct(data.total_gain_loss_pct)})
            </div>
          </div>
        </div>
      )}

      {data.items.length === 0 ? (
        <EmptyState title="Your watchlist is empty">
          <p>Open any stock from the screener and click “Add to watchlist”.</p>
        </EmptyState>
      ) : (
        <div className="panel">
          <table>
            <thead>
              <tr>
                <th className="left">Symbol</th>
                <th className="left">Name</th>
                <th>Qty</th>
                <th>Buy price</th>
                <th>Price</th>
                <th>1D %</th>
                <th>Value</th>
                <th>Gain/loss</th>
                <th>AI prob ↑</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.id} className="clickable" onClick={() => navigate(`/stocks/${item.symbol}`)}>
                  <td className="left" style={{ fontWeight: 600 }}>{item.symbol}</td>
                  <td className="left">{item.name || '—'}</td>
                  <td>{fmtNumber(item.quantity)}</td>
                  <td>{fmtMoney(item.buy_price)}</td>
                  <td>{fmtMoney(item.current_price)}</td>
                  <td className={changeClass(item.change_1d)}>{fmtPct(item.change_1d)}</td>
                  <td>{fmtMoney(item.market_value)}</td>
                  <td className={changeClass(item.gain_loss)}>
                    {item.gain_loss != null
                      ? `${fmtMoney(item.gain_loss)} (${fmtPct(item.gain_loss_pct)})`
                      : '—'}
                  </td>
                  <td>{item.ai_prob_up != null ? `${(item.ai_prob_up * 100).toFixed(1)}%` : '—'}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="btn-row">
                      <button className="secondary" onClick={() => setEditing(item)}>Edit</button>
                      <button className="danger" onClick={() => remove(item)}>✕</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <AddToWatchlistModal item={editing} onClose={() => setEditing(null)} onSaved={load} />
      )}
    </div>
  )
}
