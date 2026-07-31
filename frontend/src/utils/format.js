export function fmtMoney(value, digits = 2) {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function fmtPct(value, digits = 2) {
  if (value == null || Number.isNaN(value)) return '—'
  const pct = value * 100
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(digits)}%`
}

export function fmtNumber(value, digits = 2) {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toLocaleString('en-US', { maximumFractionDigits: digits })
}

export function fmtCompact(value) {
  if (value == null || Number.isNaN(value)) return '—'
  const abs = Math.abs(value)
  if (abs >= 1e12) return `${(value / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}K`
  return value.toFixed(0)
}

export function changeClass(value) {
  if (value == null) return ''
  return value >= 0 ? 'pos' : 'neg'
}

const CSV_COLUMNS = [
  'symbol', 'name', 'sector', 'price', 'change_1d', 'change_1w', 'change_1m',
  'change_ytd', 'rsi_14', 'pct_from_52w_high', 'avg_volume_20', 'market_cap',
  'pe_ratio', 'ai_prob_up',
]

export function downloadCsv(rows, filename = 'screener.csv') {
  if (!rows || rows.length === 0) return
  const escape = (v) => {
    if (v == null) return ''
    const s = String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const lines = [
    CSV_COLUMNS.join(','),
    ...rows.map((r) => CSV_COLUMNS.map((c) => escape(r[c])).join(',')),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
