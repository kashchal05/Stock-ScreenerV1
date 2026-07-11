import { fmtMoney, fmtPct, fmtCompact, fmtNumber } from '../utils/format.js'

export default function StatsGrid({ snapshot }) {
  const stats = [
    { label: 'Market cap', value: fmtCompact(snapshot.market_cap) },
    { label: 'P/E (trailing)', value: fmtNumber(snapshot.pe_ratio, 1) },
    { label: 'Avg volume (20d)', value: fmtCompact(snapshot.avg_volume_20) },
    { label: 'RSI (14)', value: fmtNumber(snapshot.rsi_14, 1) },
    { label: '1 week', value: fmtPct(snapshot.change_1w), cls: snapshot.change_1w },
    { label: '1 month', value: fmtPct(snapshot.change_1m), cls: snapshot.change_1m },
    { label: 'YTD', value: fmtPct(snapshot.change_ytd), cls: snapshot.change_ytd },
    { label: 'Off 52w high', value: fmtPct(snapshot.pct_from_52w_high, 1), cls: snapshot.pct_from_52w_high },
    { label: 'Above 52w low', value: fmtPct(snapshot.pct_from_52w_low, 1), cls: snapshot.pct_from_52w_low },
    { label: 'Price', value: fmtMoney(snapshot.price) },
  ]
  return (
    <div className="cards" style={{ marginBottom: 16 }}>
      {stats.map((s) => (
        <div className="card" key={s.label}>
          <div className="label">{s.label}</div>
          <div className={`value ${s.cls != null ? (s.cls >= 0 ? 'pos' : 'neg') : ''}`}>{s.value}</div>
        </div>
      ))}
    </div>
  )
}
