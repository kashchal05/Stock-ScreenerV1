import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from 'recharts'

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
            name === 'strategy' ? 'Model strategy' : 'SPY buy & hold',
          ]}
        />
        <Legend formatter={(v) => (v === 'strategy' ? 'Model strategy' : 'SPY buy & hold')} />
        <Line type="monotone" dataKey="strategy" stroke="var(--accent)" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="spy" stroke="var(--text-dim)" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
