import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from 'recharts'

const SERIES = {
  long_only: { label: 'Long-only (top 20)', color: 'var(--accent)' },
  long_short: { label: 'Long-short (market-neutral)', color: 'var(--pos)' },
  spy: { label: 'SPY buy & hold', color: 'var(--text-dim)' },
}

export default function EquityCurveChart({ curve }) {
  if (!curve || curve.length === 0) return null
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={curve} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
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
          tickFormatter={(v) => `${v.toFixed(2)}x`}
          domain={['auto', 'auto']}
          width={50}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--bg-panel)',
            border: '1px solid var(--border)',
            borderRadius: 8,
          }}
          labelStyle={{ color: 'var(--text-dim)' }}
          formatter={(value, name) => [
            value != null ? `${value.toFixed(3)}x` : '—',
            SERIES[name]?.label || name,
          ]}
        />
        <Legend formatter={(v) => SERIES[v]?.label || v} />
        {Object.entries(SERIES).map(([key, { color }]) => (
          <Line key={key} type="monotone" dataKey={key} stroke={color} strokeWidth={2} dot={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
