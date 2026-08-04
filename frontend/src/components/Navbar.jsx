import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { fetchMeta, fetchRefreshStatus, triggerRefresh } from '../api.js'
import { applyTheme, getInitialTheme } from '../utils/theme.js'
import SearchBox from './SearchBox.jsx'

export default function Navbar() {
  const [meta, setMeta] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [theme, setTheme] = useState(getInitialTheme)
  const pollRef = useRef(null)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const loadMeta = useCallback(() => {
    fetchMeta().then(setMeta).catch(() => {})
  }, [])

  useEffect(() => {
    loadMeta()
    return () => clearInterval(pollRef.current)
  }, [loadMeta])

  const startPolling = useCallback(() => {
    clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchRefreshStatus()
        if (status.status !== 'running') {
          clearInterval(pollRef.current)
          setRefreshing(false)
          loadMeta()
          window.dispatchEvent(new Event('data-refreshed'))
        }
      } catch {
        clearInterval(pollRef.current)
        setRefreshing(false)
      }
    }, 3000)
  }, [loadMeta])

  const onRefresh = async () => {
    setError(null)
    try {
      setRefreshing(true)
      await triggerRefresh()
      startPolling()
    } catch (e) {
      setRefreshing(false)
      setError(e.response?.data?.detail || 'Refresh failed')
    }
  }

  return (
    <nav className="navbar">
      <span className="brand">📈 Stock Screener</span>
      <NavLink to="/" end>Screener</NavLink>
      <NavLink to="/watchlist">Watchlist</NavLink>
      <NavLink to="/compare">Compare</NavLink>
      <NavLink to="/track-record">Track record</NavLink>
      <NavLink to="/model">AI Model</NavLink>
      <SearchBox />
      <span className="spacer" />
      {error && <span className="freshness" style={{ color: 'var(--neg)' }}>{error}</span>}
      {meta?.data_as_of && (
        <span className="freshness">Data as of {meta.data_as_of}</span>
      )}
      <button
        className="secondary icon-btn"
        onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        aria-label="Toggle theme"
      >
        {theme === 'dark' ? '☀️' : '🌙'}
      </button>
      <button className="secondary" onClick={onRefresh} disabled={refreshing}>
        {refreshing ? 'Refreshing…' : 'Refresh data'}
      </button>
    </nav>
  )
}
