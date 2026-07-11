import { useEffect, useState } from 'react'
import {
  Area,
  Bar,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchHistory } from '../api.js'
import LoadingSpinner from './LoadingSpinner.jsx'
import { fmtMoney, fmtCompact } from '../utils/format.js'

const RANGES = ['1m', '3m', '6m', '1y', '5y']

export default function PriceChart({ symbol }) {
  const [range, setRange] = useState('1y')
  // loading is derived: result is stale when it doesn't match the current request
  const [result, setResult] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchHistory(symbol, range)
      .then((d) => !cancelled && setResult({ symbol, range, bars: d.bars }))
      .catch(() => !cancelled && setResult({ symbol, range, bars: [] }))
    return () => { cancelled = true }
  }, [symbol, range])

  const loading = !result || result.symbol !== symbol || result.range !== range
  const bars = loading ? null : result.bars
  const up = bars && bars.length > 1 && bars[bars.length - 1].close >= bars[0].close
  const color = up ? 'var(--pos)' : 'var(--neg)'

  return (
    <div className="panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <h2>Price</h2>
        <div className="tabs">
          {RANGES.map((r) => (
            <button key={r} className={r === range ? 'active' : ''} onClick={() => setRange(r)}>
              {r.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      {loading ? (
        <LoadingSpinner label="Loading chart…" />
      ) : bars.length === 0 ? (
        <div className="state">No price history cached for this range.</div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={bars} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
              minTickGap={60}
            />
            <YAxis
              yAxisId="price"
              domain={['auto', 'auto']}
              tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `$${v}`}
              width={60}
            />
            <YAxis yAxisId="volume" hide domain={[0, (max) => max * 4]} />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-panel)',
                border: '1px solid var(--border)',
                borderRadius: 8,
              }}
              labelStyle={{ color: 'var(--text-dim)' }}
              formatter={(value, name) =>
                name === 'volume' ? [fmtCompact(value), 'Volume'] : [fmtMoney(value), 'Close']
              }
            />
            <Bar yAxisId="volume" dataKey="volume" fill="var(--border)" opacity={0.7} />
            <Area
              yAxisId="price"
              type="monotone"
              dataKey="close"
              stroke={color}
              strokeWidth={2}
              fill="url(#priceFill)"
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
