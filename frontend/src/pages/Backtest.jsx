import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { fetchBacktestSignals, runBacktest } from '../api.js'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import { fmtPct, fmtNumber } from '../utils/format.js'

const DEFAULT_SPEC = {
  signal: 'mom_12_1',
  direction: 'top',
  weighting: 'equal',
  top_k: 20,
  rebalance_days: 21,
  costs_bps: 10,
  capital: 10000,
}

export default function Backtest() {
  const [searchParams] = useSearchParams()
  const [signals, setSignals] = useState([])
  const [spec, setSpec] = useState(() => {
    const preset = searchParams.get('signal')
    return preset ? { ...DEFAULT_SPEC, signal: preset } : DEFAULT_SPEC
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const autoRan = useRef(false)

  // Defined before the effect so the auto-run can call it.
  const runSpec = async (raw) => {
    setLoading(true)
    setError(null)
    try {
      const payload = {
        ...raw,
        top_k: Number(raw.top_k),
        rebalance_days: Number(raw.rebalance_days),
        costs_bps: Number(raw.costs_bps),
        capital: Number(raw.capital),
      }
      setResult(await runBacktest(payload))
    } catch (err) {
      setError(err)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchBacktestSignals().then((list) => {
      setSignals(list)
      const chosen = list.find((s) => s.value === searchParams.get('signal'))
      if (chosen) {
        const preset = { ...DEFAULT_SPEC, signal: chosen.value, direction: chosen.default_direction }
        setSpec(preset)
        // Arriving with a preset (e.g. "backtest this strategy") auto-runs once.
        if (!autoRan.current) {
          autoRan.current = true
          runSpec(preset)
        }
      }
    }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const set = (key, value) => setSpec((s) => ({ ...s, [key]: value }))
  const run = (e) => {
    e?.preventDefault()
    runSpec(spec)
  }

  const m = result?.metrics
  const sig = m?.significance

  return (
    <div>
      <h1>Backtest lab</h1>
      <p className="subtitle">
        Test a rule-based strategy over history: rank the S&P 500 by a signal, hold the top names,
        rebalance, and see how it would have done — with costs and a significance test.
      </p>

      <form className="panel" onSubmit={run}>
        <div className="filter-grid">
          <div className="field">
            <label>Signal</label>
            <select value={spec.signal} onChange={(e) => {
              const chosen = signals.find((s) => s.value === e.target.value)
              setSpec((s) => ({ ...s, signal: e.target.value, direction: chosen?.default_direction || 'top' }))
            }}>
              {signals.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Pick</label>
            <select value={spec.direction} onChange={(e) => set('direction', e.target.value)}>
              <option value="top">Highest (top)</option>
              <option value="bottom">Lowest (bottom)</option>
            </select>
          </div>
          <div className="field">
            <label>Weighting</label>
            <select value={spec.weighting} onChange={(e) => set('weighting', e.target.value)}>
              <option value="equal">Equal weight</option>
              <option value="inverse_vol">Risk-based (inverse vol)</option>
            </select>
          </div>
          <div className="field">
            <label>Number of holdings</label>
            <input type="number" min="1" max="100" value={spec.top_k} onChange={(e) => set('top_k', e.target.value)} />
          </div>
          <div className="field">
            <label>Rebalance (trading days)</label>
            <input type="number" min="5" max="252" value={spec.rebalance_days} onChange={(e) => set('rebalance_days', e.target.value)} />
          </div>
          <div className="field">
            <label>Cost per side (bps)</label>
            <input type="number" min="0" max="100" value={spec.costs_bps} onChange={(e) => set('costs_bps', e.target.value)} />
          </div>
          <div className="field">
            <label>Starting capital ($)</label>
            <input type="number" min="1" value={spec.capital} onChange={(e) => set('capital', e.target.value)} />
          </div>
        </div>
        <div className="btn-row" style={{ marginTop: 14 }}>
          <button type="submit" disabled={loading}>{loading ? 'Running…' : 'Run backtest'}</button>
        </div>
      </form>

      <ErrorBanner error={error} />
      {loading && <LoadingSpinner label="Simulating… (first run builds the price cache)" />}

      {result && !loading && (
        <>
          {result.out_of_sample && (
            <div className="panel" style={{ borderColor: 'var(--pos)', background: 'rgba(46,204,113,0.08)' }}>
              ✓ <strong>Out-of-sample (leak-free):</strong> this backtests the AI model using only
              walk-forward predictions — each pick came from a model trained solely on prior data.
              It covers the walk-forward window ({result.start} → {result.end}) only.
            </div>
          )}
          {result.warnings?.map((w, i) => (
            <div key={i} className="error-banner" style={{ background: 'rgba(241,196,15,0.12)', borderColor: 'var(--warn)', color: 'var(--warn)' }}>
              ⚠ {w}
            </div>
          ))}

          <div className="cards" style={{ marginBottom: 16 }}>
            <div className="card">
              <div className="label">Total return</div>
              <div className={`value ${m.total_return >= 0 ? 'pos' : 'neg'}`}>{fmtPct(m.total_return)}</div>
            </div>
            <div className="card">
              <div className="label">vs SPY</div>
              <div className="value">{fmtPct(m.benchmark_total_return)}</div>
            </div>
            <div className="card">
              <div className="label">CAGR</div>
              <div className="value">{fmtPct(m.cagr)}</div>
            </div>
            <div className="card">
              <div className="label">Sharpe</div>
              <div className="value">{fmtNumber(m.sharpe, 2)}</div>
            </div>
            <div className="card">
              <div className="label">Sortino</div>
              <div className="value">{fmtNumber(m.sortino, 2)}</div>
            </div>
            <div className="card">
              <div className="label">Max drawdown</div>
              <div className="value neg">{fmtPct(m.max_drawdown)}</div>
            </div>
            <div className="card">
              <div className="label">Calmar</div>
              <div className="value">{fmtNumber(m.calmar, 2)}</div>
            </div>
            <div className="card">
              <div className="label">Win rate</div>
              <div className="value">{fmtPct(m.win_rate, 0)}</div>
            </div>
            <div className="card">
              <div className="label">Info ratio</div>
              <div className="value">{fmtNumber(m.information_ratio, 2)}</div>
            </div>
            <div className="card">
              <div className="label">Avg turnover</div>
              <div className="value">{fmtPct(m.avg_turnover, 0)}</div>
            </div>
          </div>

          <div className="panel">
            <h2>Equity curve ({result.start} → {result.end}, {result.n_rebalances} rebalances)</h2>
            <p style={{ color: 'var(--text-dim)', marginTop: 0 }}>
              ${Number(spec.capital).toLocaleString()} → ${Math.round(result.final_value).toLocaleString()}
            </p>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={result.equity_curve} margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
                <XAxis dataKey="date" tick={{ fill: 'var(--text-dim)', fontSize: 11 }} tickLine={false} axisLine={{ stroke: 'var(--border)' }} minTickGap={60} />
                <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v.toFixed(1)}x`} domain={['auto', 'auto']} width={46} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 8 }}
                  labelStyle={{ color: 'var(--text-dim)' }}
                  formatter={(v, name) => [`${v.toFixed(3)}x`, name === 'strategy' ? 'Strategy' : 'SPY']}
                />
                <Legend formatter={(v) => (v === 'strategy' ? 'Strategy' : 'SPY')} />
                <Line type="monotone" dataKey="strategy" stroke="var(--accent)" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="benchmark" stroke="var(--text-dim)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {sig?.mean != null && (
            <div className="panel">
              <h2>Is the edge real?</h2>
              <p style={{ margin: 0 }}>
                Per-rebalance edge over SPY ({sig.n} periods): mean <strong>{fmtPct(sig.mean)}</strong>,
                95% CI [{fmtPct(sig.ci_low)}, {fmtPct(sig.ci_high)}], p = {fmtNumber(sig.p_value, 3)}.{' '}
                <span style={{ color: sig.ci_low > 0 ? 'var(--pos)' : 'var(--text-dim)' }}>
                  {sig.ci_low > 0 ? '✓ significant at 5%' : '✗ not distinguishable from luck'}
                </span>
              </p>
            </div>
          )}

          <div className="panel">
            <h2>Latest holdings ({result.latest_rebalance})</h2>
            <div className="btn-row" style={{ flexWrap: 'wrap' }}>
              {result.latest_holdings.map((h) => (
                <span key={h.symbol} className="chip">{h.symbol}</span>
              ))}
            </div>
          </div>

          <div className="caveats">
            <strong>Honest limitations:</strong> survivorship bias (today's index members only) inflates
            historical results; costs are modeled crudely; data is daily and delayed; entry is at the
            rebalance close. This is a research tool, not investment advice.
          </div>
        </>
      )}
    </div>
  )
}
