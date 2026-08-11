import { useState } from 'react'
import { buildPlan } from '../api.js'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import { fmtMoney, fmtPct } from '../utils/format.js'

export default function Plan() {
  const [capital, setCapital] = useState('10000')
  const [positions, setPositions] = useState('')
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      setPlan(await buildPlan(Number(capital), positions ? Number(positions) : null))
    } catch (err) {
      setError(err)
      setPlan(null)
    } finally {
      setLoading(false)
    }
  }

  const mk = plan?.market
  const s = plan?.strategy
  const e = plan?.expectation

  return (
    <div>
      <h1>Build a plan</h1>
      <p className="subtitle">
        Enter an amount, and the app turns the AI model's picks, its out-of-sample track record,
        and today's market regime into a concrete, dated buy list. Illustrative — not advice.
      </p>

      <form className="panel" onSubmit={submit}>
        <div className="btn-row" style={{ flexWrap: 'wrap', gap: 16 }}>
          <div className="field">
            <label>Amount to invest ($)</label>
            <input type="number" min="1" value={capital} onChange={(ev) => setCapital(ev.target.value)} style={{ width: 180 }} />
          </div>
          <div className="field">
            <label># positions (blank = auto)</label>
            <input type="number" min="1" max="50" value={positions} onChange={(ev) => setPositions(ev.target.value)} placeholder="auto" style={{ width: 160 }} />
          </div>
          <div className="field" style={{ justifyContent: 'flex-end' }}>
            <label>&nbsp;</label>
            <button type="submit" disabled={loading}>{loading ? 'Building…' : 'Build my plan'}</button>
          </div>
        </div>
      </form>

      <ErrorBanner error={error} />
      {loading && <LoadingSpinner label="Reading the market and picking stocks…" />}

      {plan && !loading && (
        <>
          <div className="panel">
            <h2>Market environment</h2>
            <div className="detail-header" style={{ marginBottom: 8 }}>
              <span className="price" style={{ color: mk.trend_up ? 'var(--pos)' : 'var(--neg)' }}>{mk.regime}</span>
              <span style={{ color: 'var(--text-dim)' }}>as of {mk.as_of}</span>
            </div>
            <div className="cards">
              <div className="card">
                <div className="label">SPY vs 200-day avg</div>
                <div className={`value ${mk.trend_up ? 'pos' : 'neg'}`}>{fmtPct(mk.spy_vs_200d)}</div>
              </div>
              <div className="card">
                <div className="label">Volatility (annualized)</div>
                <div className="value">{fmtPct(mk.volatility_annualized, 0)}{mk.high_vol ? ' ⚠' : ''}</div>
              </div>
              <div className="card">
                <div className="label">Breadth (stocks in uptrend)</div>
                <div className="value">{mk.breadth != null ? fmtPct(mk.breadth, 0) : '—'}</div>
              </div>
            </div>
          </div>

          <div className="panel">
            <h2>The strategy</h2>
            <p style={{ marginTop: 0 }}>{s.rationale}</p>
            <div className="totals-row">
              <div className="item"><div className="label">Approach</div><div className="value" style={{ fontSize: 15 }}>{s.approach}</div></div>
            </div>
            <div className="cards" style={{ marginTop: 4 }}>
              <div className="card"><div className="label">Positions</div><div className="value">{s.num_positions}</div></div>
              <div className="card"><div className="label">Weighting</div><div className="value" style={{ fontSize: 15 }}>Equal</div></div>
              <div className="card"><div className="label">Invested</div><div className="value">{fmtMoney(plan.invested)}</div></div>
              <div className="card"><div className="label">Cash reserve</div><div className="value">{fmtMoney(plan.cash_reserve)}</div></div>
              <div className="card"><div className="label">Hold ~ / review on</div><div className="value" style={{ fontSize: 15 }}>{s.horizon_days}d · {s.review_date}</div></div>
            </div>
          </div>

          <div className="panel">
            <h2>What to buy</h2>
            <table>
              <thead>
                <tr>
                  <th className="left">Symbol</th>
                  <th className="left">Name</th>
                  <th className="left">Sector</th>
                  <th>Price</th>
                  <th>Shares</th>
                  <th>Allocation</th>
                  <th>Weight</th>
                  <th>AI ↑</th>
                </tr>
              </thead>
              <tbody>
                {plan.picks.map((p) => (
                  <tr key={p.symbol}>
                    <td className="left" style={{ fontWeight: 600 }}>{p.symbol}</td>
                    <td className="left">{p.name || '—'}</td>
                    <td className="left">{p.sector}</td>
                    <td>{fmtMoney(p.price)}</td>
                    <td>{p.shares}</td>
                    <td>{fmtMoney(p.allocation)}</td>
                    <td>{fmtPct(p.weight, 1)}</td>
                    <td>{(p.ai_prob_up * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {e && (
            <div className="panel">
              <h2>What the backtest suggests to expect</h2>
              <p style={{ margin: 0 }}>
                Over the model's out-of-sample track record ({e.n_periods} rebalances), this approach
                averaged <strong className={e.edge_per_period >= 0 ? 'pos' : 'neg'}>{fmtPct(e.edge_per_period)}</strong> per
                ~{s.horizon_days}-day period <em>above</em> the S&P 500 (a {fmtPct(e.avg_return_per_period)} gross return vs SPY's {fmtPct(e.avg_spy_per_period)}),
                with a {fmtPct(e.hit_rate, 0)} hit rate.{' '}
                <span style={{ color: e.edge_significant ? 'var(--pos)' : 'var(--text-dim)' }}>
                  {e.edge_significant
                    ? `The edge is statistically significant (95% CI ${fmtPct(e.edge_ci_low)}–${fmtPct(e.edge_ci_high)}), but modest — most of any single period is noise.`
                    : 'The edge is not statistically distinguishable from luck — treat as unproven.'}
                </span>
              </p>
            </div>
          )}

          <div className="caveats">
            <strong>Read this before acting:</strong>
            <ul>
              {plan.caveats.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          </div>
        </>
      )}
    </div>
  )
}
