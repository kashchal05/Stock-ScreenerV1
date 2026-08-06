import { useEffect, useState } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { fetchTrackRecord } from '../api.js'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { fmtPct, fmtNumber, changeClass } from '../utils/format.js'

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

  const sig = data.significance

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

      {sig?.mean != null && (
        <div className="panel">
          <h2>Is the edge real, or luck?</h2>
          <p style={{ margin: '0 0 8px' }}>
            Bootstrapping the per-rebalance edge over SPY ({sig.n} periods): mean{' '}
            <strong className={changeClass(sig.mean)}>{fmtPct(sig.mean)}</strong> per period,
            95% CI [{fmtPct(sig.ci_low)}, {fmtPct(sig.ci_high)}], p = {fmtNumber(sig.p_value, 3)}
            {sig.t_stat != null ? `, t = ${fmtNumber(sig.t_stat, 2)}` : ''}.
          </p>
          <p style={{ margin: 0, color: sig.ci_low > 0 ? 'var(--pos)' : 'var(--text-dim)' }}>
            {sig.ci_low > 0
              ? '✓ Statistically significant at the 5% level — the edge is unlikely to be pure luck (though the lower bound is close to zero, so stay humble).'
              : '✗ Not statistically distinguishable from luck at the 5% level — treat the edge as unproven.'}
          </p>
        </div>
      )}

      {data.equity_curve?.length > 0 && (
        <div className="panel">
          <h2>Cumulative performance (equal-weight, no costs)</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.equity_curve} margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: 'var(--border)' }}
                minTickGap={50}
              />
              <YAxis
                tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `${v.toFixed(1)}x`}
                domain={['auto', 'auto']}
                width={46}
              />
              <Tooltip
                contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 8 }}
                labelStyle={{ color: 'var(--text-dim)' }}
                formatter={(v, name) => [`${v.toFixed(3)}x`, name === 'strategy' ? 'Model picks' : 'SPY']}
              />
              <Legend formatter={(v) => (v === 'strategy' ? 'Model picks' : 'SPY')} />
              <Line type="monotone" dataKey="strategy" stroke="var(--accent)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="spy" stroke="var(--text-dim)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

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
