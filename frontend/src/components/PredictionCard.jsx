import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchPrediction } from '../api.js'

export default function PredictionCard({ symbol }) {
  const [pred, setPred] = useState(null)

  useEffect(() => {
    fetchPrediction(symbol).then(setPred).catch(() => setPred({ model_available: false }))
  }, [symbol])

  if (!pred) return null

  if (!pred.model_available) {
    return (
      <div className="panel">
        <h2>AI outperformance prediction</h2>
        <div className="state">
          No trained model yet. Run <code>python scripts/train_model.py</code> in the backend,
          then refresh. See <Link to="/model">AI Model</Link> for details.
        </div>
      </div>
    )
  }

  const pct = pred.prob_up * 100
  const up = pred.prob_up >= 0.5
  const color = up ? 'var(--pos)' : 'var(--neg)'
  const maxAbs = Math.max(...pred.top_contributions.map((c) => Math.abs(c.contribution)), 1e-9)

  return (
    <div className="panel">
      <h2>AI outperformance prediction</h2>
      <div className="prob-gauge">
        <span className="prob" style={{ color }}>{pct.toFixed(1)}%</span>
        <span style={{ color: 'var(--text-dim)' }}>
          chance of beating the S&P 500 median over {pred.horizon_days} trading days
        </span>
      </div>
      <div className="prob-bar-track">
        <div className="prob-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div style={{ color: 'var(--text-dim)', fontSize: 12, marginBottom: 8 }}>
        Top signals behind this prediction:
      </div>
      {pred.top_contributions.map((c) => {
        const positive = c.contribution >= 0
        const width = (Math.abs(c.contribution) / maxAbs) * 50
        return (
          <div className="contrib-row" key={c.feature}>
            <span className="contrib-label" title={c.feature}>{c.label}</span>
            <div className="contrib-track">
              <span className="mid" />
              <div
                className="contrib-bar"
                style={{
                  width: `${width}%`,
                  left: positive ? '50%' : `${50 - width}%`,
                  background: positive ? 'var(--pos)' : 'var(--neg)',
                }}
              />
            </div>
            <span className={positive ? 'pos' : 'neg'} style={{ width: 60, textAlign: 'right' }}>
              {positive ? 'up' : 'down'}
            </span>
          </div>
        )
      })}
      <div style={{ color: 'var(--text-dim)', fontSize: 11, marginTop: 12 }}>
        Model {pred.model_version} · not investment advice ·{' '}
        <Link to="/model">see honest metrics</Link>
      </div>
    </div>
  )
}
