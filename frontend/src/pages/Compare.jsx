import { useState } from 'react'
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from 'recharts'
import { fetchHistory } from '../api.js'
import ErrorBanner from '../components/ErrorBanner.jsx'
import EmptyState from '../components/EmptyState.jsx'

const COLORS = ['#4f8ef7', '#2ecc71', '#e67e22', '#e74c3c']
const RANGES = ['3m', '6m', '1y', '5y']
const MAX = 4

export default function Compare() {
  const [input, setInput] = useState('')
  const [symbols, setSymbols] = useState([])
  const [range, setRange] = useState('1y')
  const [series, setSeries] = useState({})
  const [error, setError] = useState(null)

  const addSymbol = async (e) => {
    e.preventDefault()
    const sym = input.trim().toUpperCase()
    setInput('')
    if (!sym || symbols.includes(sym) || symbols.length >= MAX) return
    setError(null)
    try {
      const data = await fetchHistory(sym, range)
      if (!data.bars.length) throw new Error(`No data for ${sym}`)
      setSeries((s) => ({ ...s, [sym]: data.bars }))
      setSymbols((s) => [...s, sym])
    } catch (err) {
      setError(err.response?.status === 404 ? `Unknown symbol: ${sym}` : err)
    }
  }

  const changeRange = async (r) => {
    setRange(r)
    const updated = {}
    await Promise.all(
      symbols.map(async (sym) => {
        const data = await fetchHistory(sym, r)
        updated[sym] = data.bars
      })
    )
    setSeries(updated)
  }

  const remove = (sym) => {
    setSymbols((s) => s.filter((x) => x !== sym))
    setSeries((s) => {
      const next = { ...s }
      delete next[sym]
      return next
    })
  }

  // Normalize each series to 100 at its first bar, then merge by date.
  const byDate = {}
  for (const sym of symbols) {
    const bars = series[sym] || []
    if (!bars.length) continue
    const base = bars[0].close
    for (const b of bars) {
      byDate[b.date] = byDate[b.date] || { date: b.date }
      byDate[b.date][sym] = (b.close / base) * 100
    }
  }
  const chartData = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))

  return (
    <div>
      <h1>Compare</h1>
      <p className="subtitle">Overlay up to {MAX} stocks, indexed to 100 at the start of the range.</p>

      <div className="panel">
        <form className="btn-row" onSubmit={addSymbol} style={{ marginBottom: 12 }}>
          <input
            placeholder="Add ticker (e.g. NVDA)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            style={{ width: 200 }}
          />
          <button type="submit" disabled={symbols.length >= MAX}>Add</button>
          <span className="spacer" style={{ flex: 1 }} />
          <div className="tabs">
            {RANGES.map((r) => (
              <button
                key={r}
                type="button"
                className={r === range ? 'active' : ''}
                onClick={() => changeRange(r)}
              >
                {r.toUpperCase()}
              </button>
            ))}
          </div>
        </form>

        <ErrorBanner error={error} />

        <div className="btn-row" style={{ marginBottom: 12, flexWrap: 'wrap' }}>
          {symbols.map((sym, i) => (
            <span key={sym} className="chip" style={{ borderColor: COLORS[i] }}>
              <span style={{ color: COLORS[i], fontWeight: 700 }}>{sym}</span>
              <span className="del" style={{ marginLeft: 8, cursor: 'pointer' }} onClick={() => remove(sym)}>✕</span>
            </span>
          ))}
        </div>

        {chartData.length === 0 ? (
          <EmptyState title="Add a ticker to start comparing">
            <p>Type a symbol above and press Add.</p>
          </EmptyState>
        ) : (
          <ResponsiveContainer width="100%" height={380}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: 'var(--border)' }}
                minTickGap={60}
              />
              <YAxis
                tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => v.toFixed(0)}
                domain={['auto', 'auto']}
                width={44}
              />
              <Tooltip
                contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 8 }}
                labelStyle={{ color: 'var(--text-dim)' }}
                formatter={(v, name) => [v != null ? v.toFixed(1) : '—', name]}
              />
              <Legend />
              {symbols.map((sym, i) => (
                <Line
                  key={sym}
                  type="monotone"
                  dataKey={sym}
                  stroke={COLORS[i]}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
