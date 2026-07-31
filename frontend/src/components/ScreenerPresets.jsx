// One-click screens. Each preset is a set of URL query params applied to the
// screener — the same params the filter form and sorting already use.
const PRESETS = [
  {
    label: '🤖 AI top picks',
    params: { min_ai_prob: '0.55', sort_by: 'ai_prob_up', sort_dir: 'desc' },
  },
  {
    label: '🚀 Momentum leaders',
    params: { min_change_1m: '0.1', sort_by: 'change_1m', sort_dir: 'desc' },
  },
  {
    label: '📉 Oversold (RSI < 30)',
    params: { max_rsi: '30', sort_by: 'rsi_14', sort_dir: 'asc' },
  },
  {
    label: '🔥 Overbought (RSI > 70)',
    params: { min_rsi: '70', sort_by: 'rsi_14', sort_dir: 'desc' },
  },
  {
    label: '🏔 Near 52-week high',
    params: { min_pct_from_52w_high: '-0.05', sort_by: 'change_1m', sort_dir: 'desc' },
  },
  {
    label: '🐘 Mega caps',
    params: { min_market_cap: '200000000000', sort_by: 'market_cap', sort_dir: 'desc' },
  },
]

export default function ScreenerPresets({ onApply }) {
  return (
    <div className="presets">
      <span className="presets-label">Quick screens:</span>
      {PRESETS.map((p) => (
        <button key={p.label} className="chip" onClick={() => onApply(p.params)}>
          {p.label}
        </button>
      ))}
    </div>
  )
}
