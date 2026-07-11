import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchScreener } from '../api.js'
import FilterPanel from '../components/FilterPanel.jsx'
import ResultsTable from '../components/ResultsTable.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import EmptyState from '../components/EmptyState.jsx'

const PAGE_SIZE = 50

export default function Screener() {
  const [searchParams, setSearchParams] = useSearchParams()
  // result is stale when its key doesn't match the current URL params
  const [result, setResult] = useState(null)
  const [refreshTick, setRefreshTick] = useState(0)

  const paramsKey = searchParams.toString()
  const params = Object.fromEntries(searchParams.entries())
  const sortBy = params.sort_by || 'market_cap'
  const sortDir = params.sort_dir || 'desc'
  const offset = Number(params.offset || 0)

  useEffect(() => {
    const bump = () => setRefreshTick((t) => t + 1)
    window.addEventListener('data-refreshed', bump)
    return () => window.removeEventListener('data-refreshed', bump)
  }, [])

  useEffect(() => {
    let cancelled = false
    const query = Object.fromEntries(new URLSearchParams(paramsKey).entries())
    fetchScreener({ ...query, limit: PAGE_SIZE })
      .then((data) => !cancelled && setResult({ key: paramsKey, data }))
      .catch((error) => !cancelled && setResult({ key: paramsKey, error }))
    return () => { cancelled = true }
  }, [paramsKey, refreshTick])

  const loading = !result || result.key !== paramsKey
  const data = loading ? null : result.data
  const error = loading ? null : result.error

  const applyFilters = (filters) => {
    setSearchParams({ ...filters, sort_by: sortBy, sort_dir: sortDir })
  }

  const onSort = (key) => {
    const next = { ...params, sort_by: key, offset: 0 }
    next.sort_dir = sortBy === key && sortDir === 'desc' ? 'asc' : 'desc'
    setSearchParams(next)
  }

  const setOffset = (nextOffset) => {
    setSearchParams({ ...params, offset: String(Math.max(0, nextOffset)) })
  }

  return (
    <div>
      <h1>Screener</h1>
      <p className="subtitle">
        Filter the S&P 500 by price, momentum, valuation, and AI trend score.
      </p>
      <FilterPanel key={paramsKey} params={params} onApply={applyFilters} />
      <ErrorBanner error={error} />
      {loading ? (
        <LoadingSpinner label="Screening stocks…" />
      ) : data && data.results.length > 0 ? (
        <div className="panel">
          <ResultsTable rows={data.results} sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <div className="pagination">
            <span>
              {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}
            </span>
            <button className="secondary" disabled={offset === 0} onClick={() => setOffset(offset - PAGE_SIZE)}>
              Prev
            </button>
            <button
              className="secondary"
              disabled={offset + PAGE_SIZE >= data.total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </div>
      ) : !error ? (
        <EmptyState title="No stocks match these filters">
          <p>Try loosening a filter, or refresh the data from the navbar.</p>
        </EmptyState>
      ) : null}
    </div>
  )
}
