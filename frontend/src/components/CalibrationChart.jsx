import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from 'recharts'

// Plots the isotonic map (raw model score -> calibrated outperformance rate)
// against the perfect-calibration diagonal.
export default function CalibrationChart({ calibration }) {
  if (!calibration?.x?.length) return null
  const data = calibration.x.map((x, i) => ({
    raw: x,
    calibrated: calibration.y[i],
    ideal: x,
  }))
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
        <XAxis
          dataKey="raw"
          type="number"
          domain={[0, 1]}
          tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
          tickFormatter={(v) => v.toFixed(1)}
          tickLine={false}
          axisLine={{ stroke: 'var(--border)' }}
          label={{ value: 'Model score', position: 'insideBottom', offset: -2, fill: 'var(--text-dim)', fontSize: 11 }}
        />
        <YAxis
          domain={[0, 1]}
          tick={{ fill: 'var(--text-dim)', fontSize: 11 }}
          tickFormatter={(v) => v.toFixed(1)}
          tickLine={false}
          axisLine={false}
          width={40}
        />
        <Tooltip
          contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 8 }}
          labelStyle={{ color: 'var(--text-dim)' }}
          formatter={(value, name) => [
            value != null ? (value * 100).toFixed(1) + '%' : '—',
            name === 'calibrated' ? 'Actual outperform rate' : 'Perfect calibration',
          ]}
          labelFormatter={(v) => `Score ${Number(v).toFixed(2)}`}
        />
        <Legend formatter={(v) => (v === 'calibrated' ? 'Calibrated' : 'Perfect')} />
        <Line type="monotone" dataKey="ideal" stroke="var(--text-dim)" strokeDasharray="4 4" strokeWidth={1} dot={false} />
        <Line type="monotone" dataKey="calibrated" stroke="var(--accent)" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
