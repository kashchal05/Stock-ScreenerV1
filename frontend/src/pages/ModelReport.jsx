import { useEffect, useState } from 'react'
import { fetchModelReport } from '../api.js'
import EquityCurveChart from '../components/EquityCurveChart.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { fmtPct, fmtNumber } from '../utils/format.js'

export default function ModelReport() {
  const [report, setReport] = useState(null)

  useEffect(() => {
    fetchModelReport().then(setReport).catch(() => setReport({ model_available: false }))
  }, [])

  if (!report) return <LoadingSpinner label="Loading model report…" />

  if (!report.model_available) {
    return (
      <div>
        <h1>AI Model</h1>
        <EmptyState title="No model trained yet">
          <p>
            Run <code>.venv/bin/python scripts/train_model.py</code> in the backend directory,
            then reload this page.
          </p>
        </EmptyState>
      </div>
    )
  }

  const agg = report.metrics?.aggregate || {}
  const folds = report.metrics?.folds || []
  const bt = report.backtest || {}
  const edge = agg.accuracy != null && agg.base_rate != null ? agg.accuracy - agg.base_rate : null

  return (
    <div>
      <h1>AI Model</h1>
      <p className="subtitle">
        {report.version} · trained {report.trained_at?.slice(0, 10)} · predicts direction over{' '}
        {report.horizon_days} trading days · {report.feature_count} features · walk-forward validated
      </p>

      <div className="cards" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="label">ROC-AUC</div>
          <div className="value">{fmtNumber(agg.roc_auc, 3)}</div>
        </div>
        <div className="card">
          <div className="label">Accuracy</div>
          <div className="value">{agg.accuracy != null ? (agg.accuracy * 100).toFixed(1) + '%' : '—'}</div>
        </div>
        <div className="card">
          <div className="label">Base rate (always up)</div>
          <div className="value">{agg.base_rate != null ? (agg.base_rate * 100).toFixed(1) + '%' : '—'}</div>
        </div>
        <div className="card">
          <div className="label">Edge over base rate</div>
          <div className={`value ${edge != null ? (edge >= 0 ? 'pos' : 'neg') : ''}`}>
            {edge != null ? fmtPct(edge, 2) : '—'}
          </div>
        </div>
        <div className="card">
          <div className="label">Hit rate at prob &gt; 0.60</div>
          <div className="value">
            {agg['precision_at_0.6'] != null ? (agg['precision_at_0.6'] * 100).toFixed(1) + '%' : '—'}
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Walk-forward folds (expanding window, {report.horizon_days}-day embargo)</h2>
        <table>
          <thead>
            <tr>
              <th className="left">Fold</th>
              <th className="left">Test window</th>
              <th>Rows</th>
              <th>Accuracy</th>
              <th>Base rate</th>
              <th>ROC-AUC</th>
              <th>Hit @ 0.60</th>
            </tr>
          </thead>
          <tbody>
            {folds.map((f) => (
              <tr key={f.fold}>
                <td className="left">{f.fold}</td>
                <td className="left">{f.test_start} → {f.test_end}</td>
                <td>{f.metrics.n_test?.toLocaleString()}</td>
                <td>{(f.metrics.accuracy * 100).toFixed(1)}%</td>
                <td>{(f.metrics.base_rate * 100).toFixed(1)}%</td>
                <td>{fmtNumber(f.metrics.roc_auc, 3)}</td>
                <td>
                  {f.metrics['precision_at_0.6'] != null
                    ? (f.metrics['precision_at_0.6'] * 100).toFixed(1) + '%'
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {bt.equity_curve && (
        <div className="panel">
          <h2>Backtest: {bt.strategy}</h2>
          <p style={{ color: 'var(--text-dim)' }}>
            {bt.start} → {bt.end} · strategy {fmtPct(bt.total_return)} vs SPY{' '}
            {fmtPct(bt.spy_total_return)} · max drawdown {fmtPct(bt.max_drawdown)} · hit rate{' '}
            {fmtPct(bt.hit_rate, 0)} over {bt.n_periods} periods
          </p>
          <EquityCurveChart curve={bt.equity_curve} />
        </div>
      )}

      <div className="caveats">
        <strong>Honest limitations</strong>
        <ul>
          {report.caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
