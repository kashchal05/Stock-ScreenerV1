import { useEffect, useState } from 'react'
import { fetchModelReport } from '../api.js'
import EquityCurveChart from '../components/EquityCurveChart.jsx'
import CalibrationChart from '../components/CalibrationChart.jsx'
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
  const lo = bt.long_only || {}
  const ls = bt.long_short || {}
  const ic = agg.rank_ic ?? bt.rank_ic

  return (
    <div>
      <h1>AI Model</h1>
      <p className="subtitle">
        {report.version} · trained {report.trained_at?.slice(0, 10)} · <strong>cross-sectional</strong> target
        (beat the S&P 500 median) over {report.horizon_days} trading days · {report.feature_count} features ·
        walk-forward validated
      </p>

      <div className="caveats" style={{ marginTop: 0, marginBottom: 16 }}>
        <strong>How to read this:</strong> the headline number is the <strong>rank information
        coefficient (IC)</strong> — the correlation between the model's ranking and what actually
        happened. IC around 0.02–0.05 is a small but genuine edge. The <strong>market-neutral
        long-short</strong> result is the honest measure of stock-picking skill; the long-only curve
        looks bigger mainly because it rides the overall market (and survivorship bias).
      </div>

      <div className="cards" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="label">Rank IC (signal quality)</div>
          <div className={`value ${ic != null ? (ic >= 0 ? 'pos' : 'neg') : ''}`}>
            {ic != null ? ic.toFixed(4) : '—'}
          </div>
        </div>
        <div className="card">
          <div className="label">ROC-AUC</div>
          <div className="value">{fmtNumber(agg.roc_auc, 3)}</div>
        </div>
        <div className="card">
          <div className="label">Accuracy vs base rate</div>
          <div className="value">
            {agg.accuracy != null ? (agg.accuracy * 100).toFixed(1) + '%' : '—'}
            <span style={{ color: 'var(--text-dim)', fontSize: 13 }}>
              {' '}/ {agg.base_rate != null ? (agg.base_rate * 100).toFixed(1) + '%' : '—'}
            </span>
          </div>
        </div>
        <div className="card">
          <div className="label">Long-short Sharpe (net)</div>
          <div className={`value ${ls.sharpe != null ? (ls.sharpe >= 0 ? 'pos' : 'neg') : ''}`}>
            {fmtNumber(ls.sharpe, 2)}
          </div>
        </div>
        <div className="card">
          <div className="label">Long-only Sharpe (net)</div>
          <div className="value">{fmtNumber(lo.sharpe, 2)}</div>
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
              <th>Rank IC</th>
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
                <td className={f.metrics.rank_ic != null ? (f.metrics.rank_ic >= 0 ? 'pos' : 'neg') : ''}>
                  {f.metrics.rank_ic != null ? f.metrics.rank_ic.toFixed(4) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {bt.equity_curve && (
        <div className="panel">
          <h2>Backtest ({bt.start} → {bt.end}, {bt.cost_per_side_bps} bps/side)</h2>
          <p style={{ color: 'var(--text-dim)' }}>
            Long-only {fmtPct(lo.total_return)} (Sharpe {fmtNumber(lo.sharpe, 2)}, maxDD {fmtPct(lo.max_drawdown)})
            {' · '}Long-short {fmtPct(ls.total_return)} (Sharpe {fmtNumber(ls.sharpe, 2)}, maxDD {fmtPct(ls.max_drawdown)})
            {' · '}SPY {fmtPct(bt.spy_total_return)}
          </p>
          <EquityCurveChart curve={bt.equity_curve} />
        </div>
      )}

      {report.calibration && (
        <div className="panel">
          <h2>Probability calibration</h2>
          <p style={{ color: 'var(--text-dim)' }}>
            Maps the model's raw score to the actual historical outperformance rate, so a
            displayed “62%” really means ~62%.
          </p>
          <CalibrationChart calibration={report.calibration} />
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
