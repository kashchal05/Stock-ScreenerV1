import { useEffect, useState } from 'react'
import { fetchIndicators } from '../api.js'
import { fmtNumber, fmtPct } from '../utils/format.js'

const ROWS = [
  { key: 'rsi_14', label: 'RSI (14)', fmt: (v) => fmtNumber(v, 1), state: rsiState },
  { key: 'macd_hist_norm', label: 'MACD histogram', fmt: (v) => fmtPct(v, 3), state: signState },
  { key: 'close_sma20_ratio', label: 'vs SMA 20', fmt: (v) => fmtPct(v, 1), state: signState },
  { key: 'close_sma50_ratio', label: 'vs SMA 50', fmt: (v) => fmtPct(v, 1), state: signState },
  { key: 'close_sma200_ratio', label: 'vs SMA 200', fmt: (v) => fmtPct(v, 1), state: signState },
  { key: 'vol_21d', label: 'Volatility (1m)', fmt: (v) => fmtPct(v, 2) },
  { key: 'atr14_norm', label: 'ATR (14) / price', fmt: (v) => fmtPct(v, 2) },
  { key: 'vol_ratio_20', label: 'Volume vs 20d avg', fmt: (v) => fmtPct(v, 1), state: signState },
  { key: 'pos_52w', label: '52-week range position', fmt: (v) => fmtPct(v, 0) },
]

function rsiState(v) {
  if (v == null) return null
  if (v >= 70) return { text: 'overbought', cls: 'neg' }
  if (v <= 30) return { text: 'oversold', cls: 'pos' }
  return { text: 'neutral', cls: '' }
}

function signState(v) {
  if (v == null) return null
  return v >= 0 ? { text: 'bullish', cls: 'pos' } : { text: 'bearish', cls: 'neg' }
}

export default function IndicatorPanel({ symbol }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    fetchIndicators(symbol).then(setData).catch(() => setData({ indicators: {} }))
  }, [symbol])

  if (!data) return null
  const ind = data.indicators || {}

  return (
    <div className="panel">
      <h2>Technical indicators</h2>
      <table>
        <tbody>
          {ROWS.map(({ key, label, fmt, state }) => {
            const value = ind[key]
            const s = state ? state(value) : null
            return (
              <tr key={key}>
                <td className="left" style={{ color: 'var(--text-dim)' }}>{label}</td>
                <td>{value != null ? fmt(value) : '—'}</td>
                <td style={{ width: 90 }}>{s ? <span className={s.cls}>{s.text}</span> : ''}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
