import { useNavigate } from 'react-router-dom'
import { fmtMoney, fmtPct, fmtCompact, fmtNumber, changeClass } from '../utils/format.js'

const COLUMNS = [
  { key: 'symbol', label: 'Symbol', left: true },
  { key: 'name', label: 'Name', left: true },
  { key: 'sector', label: 'Sector', left: true },
  { key: 'price', label: 'Price' },
  { key: 'change_1d', label: '1D %' },
  { key: 'change_1m', label: '1M %' },
  { key: 'change_ytd', label: 'YTD %' },
  { key: 'rsi_14', label: 'RSI' },
  { key: 'pct_from_52w_high', label: 'Off 52w high' },
  { key: 'avg_volume_20', label: 'Avg vol' },
  { key: 'market_cap', label: 'Mkt cap' },
  { key: 'ai_prob_up', label: 'AI prob ↑' },
]

export default function ResultsTable({ rows, sortBy, sortDir, onSort }) {
  const navigate = useNavigate()

  const arrow = (key) => (sortBy === key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '')

  return (
    <table>
      <thead>
        <tr>
          {COLUMNS.map((c) => (
            <th key={c.key} className={c.left ? 'left' : ''} onClick={() => onSort(c.key)}>
              {c.label}{arrow(c.key)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.symbol} className="clickable" onClick={() => navigate(`/stocks/${r.symbol}`)}>
            <td className="left" style={{ fontWeight: 600 }}>{r.symbol}</td>
            <td className="left">{r.name || '—'}</td>
            <td className="left">{r.sector || '—'}</td>
            <td>{fmtMoney(r.price)}</td>
            <td className={changeClass(r.change_1d)}>{fmtPct(r.change_1d)}</td>
            <td className={changeClass(r.change_1m)}>{fmtPct(r.change_1m)}</td>
            <td className={changeClass(r.change_ytd)}>{fmtPct(r.change_ytd)}</td>
            <td>{fmtNumber(r.rsi_14, 1)}</td>
            <td className={changeClass(r.pct_from_52w_high)}>{fmtPct(r.pct_from_52w_high, 1)}</td>
            <td>{fmtCompact(r.avg_volume_20)}</td>
            <td>{fmtCompact(r.market_cap)}</td>
            <td>{r.ai_prob_up != null ? `${(r.ai_prob_up * 100).toFixed(1)}%` : '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
