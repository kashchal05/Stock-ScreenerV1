import { useEffect, useState } from 'react'
import { fetchMeta } from '../api.js'

// Percent-valued filters are edited as whole percents (5 = 5%) but sent as
// fractions (0.05) to match the API.
const PERCENT_FIELDS = new Set([
  'min_change_1d', 'max_change_1d', 'min_change_1w', 'max_change_1w',
  'min_change_1m', 'max_change_1m', 'min_change_ytd', 'max_change_ytd',
  'min_pct_from_52w_high', 'max_pct_from_52w_high',
])

const FIELDS = [
  { key: 'min_price', label: 'Min price ($)' },
  { key: 'max_price', label: 'Max price ($)' },
  { key: 'min_avg_volume', label: 'Min avg volume (20d)' },
  { key: 'min_market_cap', label: 'Min market cap ($)' },
  { key: 'max_pe', label: 'Max P/E' },
  { key: 'min_rsi', label: 'Min RSI (14)' },
  { key: 'max_rsi', label: 'Max RSI (14)' },
  { key: 'min_change_1d', label: 'Min 1d change (%)' },
  { key: 'min_change_1m', label: 'Min 1m change (%)' },
  { key: 'min_change_ytd', label: 'Min YTD change (%)' },
  { key: 'max_pct_from_52w_high', label: 'Max % off 52w high' },
  { key: 'min_ai_prob', label: 'Min AI prob (0–1)' },
]

function toInputValue(key, paramValue) {
  if (paramValue == null || paramValue === '') return ''
  const num = Number(paramValue)
  return PERCENT_FIELDS.has(key) ? String(num * 100) : String(num)
}

// NOTE: the parent remounts this component (via key) when the URL params
// change, so state only needs to be initialized from params once.
export default function FilterPanel({ params, onApply }) {
  const [values, setValues] = useState(() => {
    const next = {}
    for (const { key } of FIELDS) next[key] = toInputValue(key, params[key])
    next.sector = params.sector || ''
    return next
  })
  const [sectors, setSectors] = useState([])

  useEffect(() => {
    fetchMeta().then((m) => setSectors(m.sectors)).catch(() => {})
  }, [])

  const submit = (e) => {
    e.preventDefault()
    const out = {}
    for (const { key } of FIELDS) {
      const raw = values[key]
      if (raw === '' || raw == null) continue
      const num = Number(raw)
      if (Number.isNaN(num)) continue
      out[key] = PERCENT_FIELDS.has(key) ? num / 100 : num
    }
    if (values.sector) out.sector = values.sector
    onApply(out)
  }

  const clear = () => onApply({})

  return (
    <form className="panel" onSubmit={submit}>
      <div className="filter-grid">
        {FIELDS.map(({ key, label }) => (
          <div className="field" key={key}>
            <label htmlFor={key}>{label}</label>
            <input
              id={key}
              type="number"
              step="any"
              value={values[key] ?? ''}
              onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
            />
          </div>
        ))}
        <div className="field">
          <label htmlFor="sector">Sector</label>
          <select
            id="sector"
            value={values.sector ?? ''}
            onChange={(e) => setValues((v) => ({ ...v, sector: e.target.value }))}
          >
            <option value="">All sectors</option>
            {sectors.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="btn-row" style={{ marginTop: 14 }}>
        <button type="submit">Apply filters</button>
        <button type="button" className="secondary" onClick={clear}>Clear</button>
      </div>
    </form>
  )
}
