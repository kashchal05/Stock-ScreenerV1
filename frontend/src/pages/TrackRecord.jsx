import { useEffect, useState } from 'react'
import { fetchTrackRecord } from '../api.js'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { fmtPct, changeClass } from '../utils/format.js'

export default function TrackRecord() {
  const [data, setData] = useState(null)

  useEffect(() => {
    fetchTrackRecord().then(setData).catch(() => setData({ available: false }))
  }, [])

  if (!data) return <LoadingSpinner label="Loading track record…" />

  if (!data.available) {
    return (
      <div>
        <h1>Track record</h1>
        <EmptyState title="No track record yet">
          <p>
            Run <code>.venv/bin/python scripts/seed_picks.py</code> to seed the out-of-sample
            record, then reload. Live picks are logged automatically on each data refresh.
          </p>
        </EmptyState>
      </div>
    )
  }

  return (
    <div>
      <h1>Track record</h1>
      <p className="subtitle">
        The model's top {data.top_k} picks on each {data.horizon_days}-day rebalance, and how they
        actually did. Seeded from leak-free walk-forward predictions; live picks accrue on refresh.
      </p>

      <div className="caveats" style={{ marginTop: 0, marginBottom: 16 }}>
        <strong>Out-of-sample by construction:</strong> each backtested pick came from a model
        trained only on data before that date — no hindsight. Still subject to survivorship bias
        (current index members) and excludes trading costs. Not investment advice.
      </div>

      <div className="cards" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="label">Avg return / pick</div>
          <div className={`value ${changeClass(data.avg_pick_return)}`}>
            {fmtPct(data.avg_pick_return)}
          </div>
        </div>
        <div className="card">
          <div className="label">vs SPY (same windows)</div>
          <div className="value">{fmtPct(data.avg_spy_return)}</div>
        </div>
        <div className="card">
          <div className="label">Edge over SPY</div>
          <div className={`value ${changeClass(data.edge)}`}>{fmtPct(data.edge)}</div>
        </div>
        <div className="card">
          <div className="label">Hit rate</div>
          <div className="value">{data.hit_rate != null ? (data.hit_rate * 100).toFixed(1) + '%' : '—'}</div>
        </div>
        <div className="card">
          <div className="label">Picks tracked</div>
          <div className="value">
            {data.n_settled} <span style={{ color: 'var(--text-dim)', fontSize: 13 }}>/ {data.n_picks}</span>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Recent rebalances</h2>
        <table>
          <thead>
            <tr>
              <th className="left">Date</th>
              <th className="left">Source</th>
              <th>Picks</th>
              <th>Avg return</th>
              <th>SPY</th>
              <th>Edge</th>
              <th className="left">Top holdings</th>
            </tr>
          </thead>
          <tbody>
            {data.periods.map((p) => {
              const edge = p.avg_return != null && p.spy_return != null ? p.avg_return - p.spy_return : null
              const top5 = p.picks.slice(0, 5).map((x) => x.symbol).join(', ')
              return (
                <tr key={p.date}>
                  <td className="left">{p.date}</td>
                  <td className="left">
                    <span style={{ color: p.source === 'live' ? 'var(--accent)' : 'var(--text-dim)' }}>
                      {p.source}
                    </span>
                  </td>
                  <td>{p.n_picks}</td>
                  <td className={changeClass(p.avg_return)}>{p.settled ? fmtPct(p.avg_return) : 'pending'}</td>
                  <td>{fmtPct(p.spy_return)}</td>
                  <td className={changeClass(edge)}>{edge != null ? fmtPct(edge) : '—'}</td>
                  <td className="left" style={{ color: 'var(--text-dim)' }}>{top5}…</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
